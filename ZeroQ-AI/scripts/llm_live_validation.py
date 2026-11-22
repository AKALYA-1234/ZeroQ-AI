#!/usr/bin/env python3
"""
Live LLM validation against the labelled multilingual evaluation set (real API calls).

  python scripts/llm_live_validation.py --out llm_validation.json [--limit N]

1. Accuracy: ML-only vs LLM-only (primary provider, no failover) vs the full pipeline decision rule
   (ML when confident, otherwise LLM) — category level, per language. The labelled set is an
   independent test set, NOT admin-verified real outcomes.
2. Translation quality signal: does the LLM translation preserve identifiers (batch / machine IDs)?
3. Fault injection with real providers: primary timeout → failover; invalid primary key → failover;
   every provider failing → LLMUnavailable (nothing fabricated).
4. Usage: calls, tokens, latency, billing class and estimated cost per provider.
Bulk calls use the primary provider only, to respect secondary free-tier caps.
"""
import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from pydantic import SecretStr  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.database.connection import SessionLocal  # noqa: E402
from app.intelligence import llm  # noqa: E402
from app.intelligence.eval_dataset import EVAL_ITEMS, UNSUPPORTED_OFFLINE  # noqa: E402
from app.intelligence.learning import get_classifier  # noqa: E402
from app.intelligence.understanding import understand  # noqa: E402

PACE_SECONDS = 0.5          # gentle pacing between bulk calls
IDENTIFIER_CASES = [("BAT000123 batch la line M-12 machine romba heat aguthu", ["BAT000123", "M-12"]),
                    ("Batch BAT004521 ke packet mein keede the, machine L3 band ho gayi", ["BAT004521", "L3"])]


def llm_only(text, usage):
    try:
        out = llm.analyze_issue(text, text, "auto-detect", [], [], None, usage_log=usage)
        return out.category, out.confidence
    except llm.LLMUnavailable as exc:
        return None, str(exc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="llm_validation.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    primary = settings.LLM_PROVIDER
    db = SessionLocal()
    clf = get_classifier(db)
    db.close()
    items = EVAL_ITEMS + UNSUPPORTED_OFFLINE
    if args.limit:
        items = items[: args.limit]

    # Bulk runs: primary provider only (no failover).
    settings.LLM_FAILOVER_ENABLED = False
    usage, rows = [], []
    for text, lang, expected, group in items:
        u = understand(text, allow_llm=False)
        ml = clf.predict(u["english_text"])
        llm_cat, llm_conf = llm_only(text, usage)
        confident = ml["category_confidence"] >= settings.ML_CONFIDENCE_THRESHOLD
        pipeline = ml["category"] if confident else (llm_cat or None)
        rows.append({"text": text, "language": lang, "expected": expected, "offline_supported": (text, lang, expected, group) in EVAL_ITEMS,
                     "ml": ml["category"], "ml_confidence": ml["category_confidence"], "llm": llm_cat,
                     "pipeline": pipeline, "pipeline_used_llm": not confident})
        time.sleep(PACE_SECONDS)

    def acc(key, subset):
        n = len(subset)
        return {"n": n, "accuracy": round(sum(r[key] == r["expected"] for r in subset) / n, 4) if n else None}
    supported = [r for r in rows if r["offline_supported"]]
    unsupported = [r for r in rows if not r["offline_supported"]]
    by_lang = defaultdict(list)
    for r in rows:
        by_lang[r["language"]].append(r)
    accuracy = {
        "supported_languages": {k: acc(k, supported) for k in ("ml", "llm", "pipeline")},
        "unsupported_offline_languages": {k: acc(k, unsupported) for k in ("ml", "llm", "pipeline")},
        "by_language": {l: {k: acc(k, rs)["accuracy"] for k in ("ml", "llm", "pipeline")} | {"n": len(rs)}
                        for l, rs in sorted(by_lang.items())},
        "pipeline_llm_share": round(sum(r["pipeline_used_llm"] for r in rows) / len(rows), 4),
        "disagreements": [r for r in rows if r["ml"] != r["llm"]][:20],
    }

    # Identifier preservation in translation.
    ids = []
    for text, must_keep in IDENTIFIER_CASES:
        try:
            tr = llm.translate(text, "auto-detect", usage_log=usage)
            ids.append({"text": text, "translation": tr, "kept": {i: i in tr for i in must_keep}})
        except llm.LLMUnavailable as exc:
            ids.append({"text": text, "error": str(exc)})

    # Fault injection with real providers (failover enabled).
    settings.LLM_FAILOVER_ENABLED = True
    faults = {}
    real_timeout = settings.LLM_TIMEOUT_SECONDS
    try:
        llm.reset_circuit()
        settings.LLM_TIMEOUT_SECONDS = 0.001
        settings.LLM_MAX_RETRIES = 0
        f_usage = []
        try:
            llm.translate("Packet la poochi irundhuchu", "Tanglish", usage_log=f_usage)
            faults["all_timeouts"] = {"unexpected_success": True, "attempts": f_usage}
        except llm.LLMUnavailable as exc:
            faults["all_timeouts"] = {"raised_LLMUnavailable": True, "message": str(exc),
                                      "attempts": [(a["provider"], a.get("error")) for a in f_usage]}
    finally:
        settings.LLM_TIMEOUT_SECONDS = real_timeout
        settings.LLM_MAX_RETRIES = 2

    real_key = settings.GROQ_API_KEY
    try:
        llm.reset_circuit()
        settings.GROQ_API_KEY = SecretStr("gsk_invalid_key_for_validation")
        f_usage = []
        try:
            tr = llm.translate("Packet la poochi irundhuchu", "Tanglish", usage_log=f_usage)
            faults["invalid_primary_key_failover"] = {
                "translation": tr, "attempts": [(a["provider"], a.get("status"), a.get("error"), a.get("latency_ms"))
                                                for a in f_usage]}
        except llm.LLMUnavailable as exc:
            faults["invalid_primary_key_failover"] = {"raised": str(exc),
                                                      "attempts": [(a["provider"], a.get("error")) for a in f_usage]}
        usage.extend(a for a in f_usage if a.get("status") == "ok")
    finally:
        settings.GROQ_API_KEY = real_key
        llm.reset_circuit()

    # Usage summary.
    per = defaultdict(lambda: {"calls": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0, "latency": [],
                               "billing": set(), "cost": 0.0, "cost_unknown_calls": 0})
    for u in usage:
        p = per[u.get("provider")]
        if u.get("status") != "ok":
            p["errors"] += 1
            continue
        p["calls"] += 1
        p["input_tokens"] += u["input_tokens"]
        p["output_tokens"] += u["output_tokens"]
        p["latency"].append(u["latency_ms"])
        p["billing"].add(u["billing"])
        if u["estimated_cost_usd"] is None:
            p["cost_unknown_calls"] += 1
        else:
            p["cost"] += u["estimated_cost_usd"]
    usage_summary = {k: {"calls": v["calls"], "errors": v["errors"], "input_tokens": v["input_tokens"],
                         "output_tokens": v["output_tokens"],
                         "latency_p50_ms": statistics.median(v["latency"]) if v["latency"] else None,
                         "latency_max_ms": max(v["latency"]) if v["latency"] else None,
                         "billing": sorted(v["billing"]),
                         # None (unknown) unless every call had a known price; never a misleading 0.0
                         "estimated_cost_usd": round(v["cost"], 6) if not v["cost_unknown_calls"] else None,
                         "known_cost_subtotal_usd": round(v["cost"], 6),
                         "calls_with_unknown_cost": v["cost_unknown_calls"]} for k, v in per.items()}
    report = {"primary_provider": primary, "models": {"groq": settings.GROQ_MODEL, "openrouter": settings.OPENROUTER_MODEL},
              "accuracy": accuracy, "identifier_preservation": ids, "fault_injection": faults,
              "usage": usage_summary, "rows": rows}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: report[k] for k in ("accuracy", "identifier_preservation", "fault_injection", "usage")},
                     ensure_ascii=False, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
