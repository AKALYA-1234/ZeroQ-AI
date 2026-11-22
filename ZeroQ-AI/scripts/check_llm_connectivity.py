#!/usr/bin/env python3
"""
Live connectivity check for each LLM provider, tested INDEPENDENTLY (no failover).

  python scripts/check_llm_connectivity.py                 # every configured provider
  python scripts/check_llm_connectivity.py --provider groq

Per provider: (1) structured translation round-trip (Tanglish → English, schema-validated),
(2) structured issue analysis of an unfamiliar complaint. Reports model, latency, tokens,
billing class and estimated cost. Makes real API calls (free-tier or billed, depending on
your account/model). Never prints keys. Exit code 0 only if every tested provider passes.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.intelligence import llm  # noqa: E402
from app.intelligence.llm_providers import ProviderError  # noqa: E402

TANGLISH = "Machine romba heat aguthu, production output kammiya irukku."
UNFAMILIAR = "The QR code printed on every carton scans to a 404 page, and the date ink smudges in humid weather."


def openrouter_key_info() -> str:
    key = settings.OPENROUTER_API_KEY.get_secret_value() if settings.OPENROUTER_API_KEY else ""
    if not key:
        return "n/a"
    try:
        r = httpx.get(f"{settings.OPENROUTER_BASE_URL}/key", headers={"Authorization": f"Bearer {key}"}, timeout=15)
        if r.status_code != 200:
            return f"key info unavailable (HTTP {r.status_code})"
        d = r.json().get("data", {})
        return (f"is_free_tier={d.get('is_free_tier')} usage={d.get('usage')} "
                f"limit={d.get('limit')} limit_remaining={d.get('limit_remaining')}")
    except httpx.HTTPError as exc:
        return f"key info unavailable ({type(exc).__name__})"


def check(name: str) -> bool:
    provider = llm._build(name)
    print(f"\n== {name}  model={provider.model}  configured={provider.configured}")
    if not provider.configured:
        print("   SKIP: no key / model configured")
        return True
    if name == "openrouter":
        print(f"   account: {openrouter_key_info()}")
    ok = True
    for op, schema, system, user, tokens in (
        ("translate", llm.LLMTranslation, "Translate this complaint into plain English. Reply as JSON.",
         f"<complaint>{TANGLISH}</complaint>", llm.TRANSLATE_MAX_TOKENS),
        ("analyze", llm.LLMIssueAnalysis,
         "You are a food-manufacturing quality engineer. Analyse the complaint. Allowed categories: "
         + ", ".join(llm.CATEGORIES) + ". Allowed severities: low, medium, high, critical. Reply as JSON.",
         f"<complaint>{UNFAMILIAR}</complaint>", llm.ANALYZE_MAX_TOKENS),
    ):
        try:
            result = provider.complete(op, system, user, schema, tokens, "low")
        except ProviderError as exc:
            print(f"   FAIL {op}: {exc.kind}")
            ok = False
            continue
        u = result.usage
        summary = (result.parsed.english_text if op == "translate"
                   else f"{result.parsed.category} / {result.parsed.subcategory} (conf {result.parsed.confidence})")
        print(f"   PASS {op}: {summary[:90]!r}")
        print(f"        served_by={u['model']} latency={u['latency_ms']}ms tokens={u['input_tokens']}+{u['output_tokens']} "
              f"retries={u['retries']} output={u['structured_output']} billing={u['billing']} "
              f"cost={u['estimated_cost_usd']}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["groq", "openrouter", "anthropic", "all"], default="all")
    args = ap.parse_args()
    print(f"LLM_ENABLED={settings.LLM_ENABLED} order={llm.provider_order()} failover={settings.LLM_FAILOVER_ENABLED}")
    names = list(llm.KNOWN_PROVIDERS) if args.provider == "all" else [args.provider]
    results = {n: check(n) for n in names}
    print("\nRESULT:", ", ".join(f"{n}={'ok' if r else 'FAILED'}" for n, r in results.items()))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
