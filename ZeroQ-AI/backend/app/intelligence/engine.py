"""
Issue prediction engine — orchestrates the full pipeline for one complaint:

  understand (language → English → symptoms/entities)
  → ML classifier → historical retrieval (evidence)
  → confidence evaluation
      confident & familiar → source "ml"
      otherwise            → LLM fallback (source "llm") if configured,
                             else symptom rules (source "rules"),
                             else the ML best guess flagged low-confidence
  → severity from historical evidence + safety escalation + batch risk
  → persisted as IssueAnalysis (one row per complaint, original text preserved)
"""
import logging
import re
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.intelligence import llm
from app.intelligence.learning import get_classifier
from app.intelligence.retrieval import get_index
from app.intelligence.taxonomy import SEVERITIES, category_for
from app.intelligence.understanding import understand
from app.models.complaint import Complaint
from app.models.intelligence import IssueAnalysis

logger = logging.getLogger(__name__)

RULES_MAX_CONFIDENCE = 0.5
SUBCATEGORY_MAX = 120   # issue_analyses.predicted_subcategory length
CRITICAL_TERMS = r"(sick|ill\b|illness|vomit|hospital|injur|chok|allerg|diarrh|food poison)"
HIGH_TERMS = r"(glass|metal|blade|sharp|child|baby|infant|mou?ld|contaminat)"
SAFETY_CATEGORIES = {"Foreign Matter / Contamination", "Infestation"}


def compose_text(complaint: Complaint) -> str:
    parts = [p.strip() for p in (complaint.title, complaint.description) if p and p.strip()]
    if len(parts) == 2 and parts[1].lower().startswith(parts[0].lower()):
        parts = parts[1:]
    return ". ".join(parts)


def _bump(level: str, steps: int = 1) -> str:
    i = SEVERITIES.index(level) if level in SEVERITIES else 1
    return SEVERITIES[min(len(SEVERITIES) - 1, i + steps)]


def assess_severity(evidence: dict, category: Optional[str], text: str,
                    batch_risk: Optional[dict]) -> Tuple[str, List[str]]:
    basis = []
    dist = evidence.get("severity_distribution") or {}
    if dist:
        level = max(dist, key=dist.get)
        basis.append(f"Most common severity among similar incidents: {level} ({dist[level]:.0%})")
    else:
        level = "medium"
        basis.append("No historical severity evidence; defaulted to medium")
    low = (text or "").lower()
    if re.search(CRITICAL_TERMS, low):
        level = "critical"
        basis.append("Consumer-health terms present (illness/injury/allergy) → critical")
    elif re.search(HIGH_TERMS, low) or category in SAFETY_CATEGORIES:
        if SEVERITIES.index(level) < SEVERITIES.index("high"):
            level = "high"
            basis.append("Food-safety category or hazard terms → at least high")
    if batch_risk and batch_risk.get("is_high_risk"):
        level = _bump(level)
        basis.append(f"Batch flagged high-risk by XGBoost (p={batch_risk.get('complaint_probability')}) → +1 level")
    return level, basis


def _batch_risk(complaint: Complaint, entities: dict) -> Optional[dict]:
    batch_code = complaint.batch.batch_id if complaint.batch else entities.get("batch_id")
    if not batch_code:
        return None
    try:
        from app.ml.model_service import predict_batch
        res = predict_batch(batch_code)
        if res.get("status") != "success":
            return None
        return {k: res.get(k) for k in ("batch_id", "complaint_probability", "is_high_risk",
                                        "risk_level", "model_version")} | {"batch_id": batch_code}
    except Exception as exc:
        logger.warning("Batch risk unavailable for %s: %s", batch_code, exc)
        return None


def _rules_prediction(symptoms: List[dict]) -> Optional[dict]:
    if not symptoms:
        return None
    sub = symptoms[0]["subcategory_hint"]
    return {
        "category": category_for(sub), "subcategory": sub,
        "confidence": min(RULES_MAX_CONFIDENCE, 0.3 + 0.1 * len(symptoms)),
        "checks": [s["suggested_checks"] for s in symptoms],
    }


def run_analysis(db: Session, complaint: Complaint, allow_llm: bool = True) -> IssueAnalysis:
    text = compose_text(complaint)
    llm_usage: list = []
    # This complaint's own customer identifiers are redacted before any external LLM call.
    pii_terms = tuple(t for t in (complaint.customer_name, complaint.customer_email,
                                  complaint.customer_contact, complaint.customer_organization) if t)
    u = understand(text, allow_llm=allow_llm, usage_log=llm_usage, pii_terms=pii_terms)
    english = u["english_text"]
    symptoms = u["symptoms"]

    ml = get_classifier(db).predict(english)
    index = get_index(db)
    search = index.search(english, subcategory=ml["subcategory"], product_id=complaint.product_id,
                          exclude_complaint_pk=complaint.id, category=ml["category"])
    batch_risk = _batch_risk(complaint, u["entities"])

    low_conf = ml["category_confidence"] < settings.ML_CONFIDENCE_THRESHOLD
    unfamiliar = search["best_similarity"] < settings.MIN_HISTORICAL_SIMILARITY
    reasons = []
    if low_conf:
        reasons.append(f"ML confidence {ml['category_confidence']:.2f} < {settings.ML_CONFIDENCE_THRESHOLD}")
    if unfamiliar:
        reasons.append(f"best historical similarity {search['best_similarity']:.2f} < "
                       f"{settings.MIN_HISTORICAL_SIMILARITY} (unfamiliar issue)")
    if search["category_matches"] == 0:
        reasons.append(f"no resolved historical incidents in category '{ml['category']}' (new kind of issue)")

    source, category, subcategory = "ml", ml["category"], ml["subcategory"]
    confidence, llm_result, root_cause, recommendation = ml["category_confidence"], None, None, None

    if reasons:
        llm_out = None
        if allow_llm and llm.is_llm_available():
            try:
                llm_out = llm.analyze_issue(
                    u["original_text"], english, u["language"]["name"],
                    [s["symptom"] for s in symptoms], search["incidents"],
                    complaint.product.name if complaint.product else None, usage_log=llm_usage,
                    pii_terms=pii_terms)
            except llm.LLMUnavailable as exc:
                reasons.append(f"LLM unavailable: {exc}")
        if llm_out is not None:
            # LLM free text is clipped to the column size (PostgreSQL enforces VARCHAR limits).
            source, category, subcategory = "llm", llm_out.category, (llm_out.subcategory or "")[:SUBCATEGORY_MAX] or None
            confidence, llm_result = llm_out.confidence, llm_out.model_dump()
            served = next((u_ for u_ in reversed(llm_usage)
                           if u_.get("operation") == "analyze" and u_.get("status") == "ok"), {})
            llm_result.update(provider=served.get("provider"), model=served.get("model"))
            root_cause, recommendation = llm_out.probable_root_cause, llm_out.recommended_resolution
            # Adopt the LLM's translation only when we had no real one (offline gloss / none available).
            # Never for English input: the LLM saw a redacted copy and would echo [EMAIL]/[PHONE] tokens.
            if u["translation_method"] in ("glossary", "unavailable") and llm_out.english_translation:
                english = llm_out.english_translation
        else:
            rules = _rules_prediction(symptoms)
            # Rules replace the ML guess when ML is unsure or disagrees with the symptoms.
            if rules and (low_conf or rules["category"] != ml["category"]):
                source, category, subcategory = "rules", rules["category"], rules["subcategory"]
                confidence = rules["confidence"]
                recommendation = " ".join(rules["checks"])
            elif low_conf and ml["category_confidence"] < settings.ML_MIN_GUESS_CONFIDENCE:
                # Nothing supports a category (weak ML guess, no LLM, no symptom rule):
                # leave it undetermined for the admin instead of presenting a guess.
                source, category, subcategory = "undetermined", None, None
                reasons.append("no reliable prediction: left undetermined for admin assessment")
        if allow_llm and not llm.is_configured():
            reasons.append("LLM fallback not configured")
        if source not in ("ml", "undetermined") and subcategory != ml["subcategory"]:
            search = index.search(english, subcategory=subcategory, product_id=complaint.product_id,
                                  exclude_complaint_pk=complaint.id, category=category)

    undetermined = source == "undetermined"
    evidence = {"root_causes": [], "resolutions": [], "severity_distribution": {}} if undetermined         else search["evidence"]
    # Historical root causes / actions count as evidence only when comparable incidents
    # (same category, similar enough text) exist; otherwise recommend symptom checks.
    comparable = (not undetermined and search["category_matches"] > 0
                  and search["best_similarity"] >= settings.MIN_HISTORICAL_SIMILARITY)
    if root_cause is None and comparable:
        root_cause = evidence["root_causes"][0]["root_cause"] if evidence["root_causes"] else None
    if recommendation is None:
        if not comparable and symptoms:
            recommendation = " ".join(dict.fromkeys(s["suggested_checks"] for s in symptoms))
        elif evidence["resolutions"]:
            recommendation = evidence["resolutions"][0]["action"]
    severity, severity_basis = assess_severity(evidence, category, english, batch_risk)
    if undetermined and len(severity_basis) == 1:
        # Only the "no evidence" default fired — don't present a guessed severity.
        severity, severity_basis = None, ["Not assessed: no evidence for a severity"]
    if llm_result and severity and SEVERITIES.index(llm_result["severity"]) > SEVERITIES.index(severity):
        severity = llm_result["severity"]
        severity_basis.append(f"LLM assessed {severity}")

    if llm_usage:  # token usage + cost estimate for every LLM call made for this complaint
        llm_result = {**(llm_result or {}), "usage": llm_usage}
    products = u["entities"].get("products") or []
    affected = complaint.product.name if complaint.product else (products[0] if products else None)
    fields = dict(
        original_text=u["original_text"], detected_language=u["language"]["code"],
        language_name=u["language"]["name"], is_code_mixed=u["language"]["is_code_mixed"],
        english_text=english, translation_method=u["translation_method"],
        symptoms=symptoms, entities=u["entities"] | {"language_evidence": u["language"]["evidence"]},
        prediction_source=source, predicted_category=category, predicted_subcategory=subcategory,
        predicted_root_cause=root_cause, predicted_severity=severity, affected_product=affected,
        recommended_resolution=recommendation, confidence=round(float(confidence), 4),
        is_low_confidence=bool(reasons), fallback_reason="; ".join(reasons) or None,
        ml_result=ml | {"severity_basis": severity_basis}, llm_result=llm_result, batch_risk=batch_risk,
        similar_incidents=search["incidents"],
        root_cause_distribution=evidence["root_causes"],
        resolution_options=evidence["resolutions"],
        model_version=ml["model_version"], status="completed", error=None,
        updated_at=datetime.utcnow(),
    )
    analysis = db.query(IssueAnalysis).filter(IssueAnalysis.complaint_id == complaint.id).first()
    if analysis is None:
        analysis = IssueAnalysis(complaint_id=complaint.id, **fields)
        db.add(analysis)
    else:
        for k, v in fields.items():
            setattr(analysis, k, v)
    if not complaint.category:
        complaint.category = category
        complaint.complaint_subcategory = subcategory
    db.commit()
    db.refresh(analysis)
    return analysis


def analyze_text_preview(db: Session, text: str, allow_llm: bool = False) -> dict:
    """Dry-run the understanding + ML + retrieval steps on raw text (nothing persisted)."""
    u = understand(text, allow_llm=allow_llm)
    ml = get_classifier(db).predict(u["english_text"])
    search = get_index(db).search(u["english_text"], subcategory=ml["subcategory"], top_k=5)
    return {"understanding": u, "ml": ml, "best_similarity": search["best_similarity"],
            "similar_incidents": search["incidents"], "evidence": search["evidence"],
            "would_fallback": ml["category_confidence"] < settings.ML_CONFIDENCE_THRESHOLD
            or search["best_similarity"] < settings.MIN_HISTORICAL_SIMILARITY}
