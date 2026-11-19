"""
Claude-backed fallback for translation and low-confidence / unfamiliar issues.

The LLM is only consulted when it is configured (ANTHROPIC_API_KEY or
ANTHROPIC_AUTH_TOKEN set and LLM_ENABLED=true). Output is schema-validated via
structured outputs and is always stored as `prediction_source = "llm"` so the
admin can distinguish it from ML predictions and verified resolutions.
"""
import importlib.util
import json
import logging
import os
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.config import settings
from app.intelligence.taxonomy import CATEGORIES, SEVERITIES

logger = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_CONTEXT_INCIDENTS = 5
TRANSLATE_MAX_TOKENS = 2000
ANALYZE_MAX_TOKENS = 4000

_client = None


class LLMUnavailable(Exception):
    pass


class LLMTranslation(BaseModel):
    english_text: str = Field(description="Faithful English translation of the complaint")


class LLMIssueAnalysis(BaseModel):
    english_translation: str
    issue_summary: str = Field(description="One sentence: what actually went wrong")
    symptoms: List[str]
    category: str = Field(description=f"One of: {', '.join(CATEGORIES)}")
    subcategory: str
    probable_root_cause: str
    severity: str = Field(description=f"One of: {', '.join(SEVERITIES)}")
    affected_product: Optional[str] = None
    recommended_resolution: str
    confidence: float = Field(ge=0.0, le=1.0, description="Self-assessed confidence 0-1")
    reasoning: str = Field(description="Short justification referencing the evidence used")


def set_client(client) -> None:
    """Inject a client (tests) or reset to None."""
    global _client
    _client = client


def is_llm_available() -> bool:
    if _client is not None:
        return True
    if not settings.LLM_ENABLED:
        return False
    if importlib.util.find_spec("anthropic") is None:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not is_llm_available():
        raise LLMUnavailable("LLM fallback is not configured")
    import anthropic
    _client = anthropic.Anthropic(timeout=settings.LLM_TIMEOUT_SECONDS, max_retries=2)
    return _client


def _parse(system: str, user: str, schema, max_tokens: int, effort: str):
    client = _get_client()
    try:
        response = client.beta.messages.parse(
            model=settings.LLM_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except Exception as exc:  # network / API errors are surfaced as unavailability
        logger.warning("LLM request failed: %s", exc)
        raise LLMUnavailable(f"LLM request failed: {type(exc).__name__}") from exc
    if response.stop_reason == "refusal":
        raise LLMUnavailable("LLM declined the request")
    if response.parsed_output is None:
        raise LLMUnavailable("LLM returned no structured output")
    return response.parsed_output


def translate(text: str, language_name: str) -> str:
    system = ("You translate customer and plant-floor quality complaints into plain English. "
              "The text may mix languages or be romanised (e.g. Tanglish, Hinglish). "
              "Translate faithfully; do not add information or interpret beyond the text.")
    out = _parse(system, f"Language hint: {language_name}\n\nText:\n{text}",
                 LLMTranslation, TRANSLATE_MAX_TOKENS, "low")
    return out.english_text.strip()


def _incident_context(incidents: List[dict]) -> str:
    rows = []
    for inc in incidents[:MAX_CONTEXT_INCIDENTS]:
        rows.append({
            "description": inc.get("description"), "category": inc.get("category"),
            "subcategory": inc.get("subcategory"), "root_cause": inc.get("root_cause"),
            "resolution": inc.get("resolution"), "outcome": inc.get("effectiveness"),
            "similarity": inc.get("similarity"),
        })
    return json.dumps(rows, ensure_ascii=False)


def analyze_issue(original_text: str, english_text: str, language_name: str,
                  symptoms: List[str], incidents: List[dict], product: Optional[str]) -> LLMIssueAnalysis:
    system = (
        "You are a food-manufacturing quality engineer triaging complaints. Identify the actual "
        "problem, not keywords. Use the historical incidents only as evidence; if none fit, say the "
        "issue looks new and choose 'Other / New Issue' or the closest category. Base severity on "
        "consumer-safety risk (foreign matter, contamination, illness = high/critical) and the "
        "historical evidence. Be conservative with confidence: an admin will verify your answer.\n"
        f"Allowed categories: {', '.join(CATEGORIES)}.\nAllowed severities: {', '.join(SEVERITIES)}."
    )
    user = (
        f"Original complaint ({language_name}):\n{original_text}\n\n"
        f"Working English text:\n{english_text}\n\n"
        f"Product on the complaint form: {product or 'not specified'}\n"
        f"Symptoms detected by rules: {', '.join(symptoms) or 'none'}\n\n"
        f"Most similar historical incidents (JSON):\n{_incident_context(incidents)}"
    )
    result = _parse(system, user, LLMIssueAnalysis, ANALYZE_MAX_TOKENS, "medium")
    if result.category not in CATEGORIES:
        result.category = "Other / New Issue"
    if result.severity not in SEVERITIES:
        result.severity = "medium"
    return result
