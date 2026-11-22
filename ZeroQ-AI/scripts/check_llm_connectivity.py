#!/usr/bin/env python3
"""
Live check of the LLM fallback provider (makes real, billed API calls: ~2 small requests).

  python scripts/check_llm_connectivity.py

Reports: configuration, model availability, a structured translation round-trip,
latency, token usage and estimated cost. Exits non-zero on failure. Prints no secrets.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.config import settings  # noqa: E402
from app.intelligence import llm  # noqa: E402


def main() -> int:
    print(f"LLM_ENABLED={settings.LLM_ENABLED}  LLM_MODEL={settings.LLM_MODEL}")
    if not llm.is_configured():
        print("NOT CONFIGURED: set ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN) in the backend environment "
              "and install the `anthropic` package. The system will use the offline glossary + symptom rules.")
        return 2
    import anthropic
    client = anthropic.Anthropic(timeout=settings.LLM_TIMEOUT_SECONDS, max_retries=1)
    try:
        model = client.models.retrieve(settings.LLM_MODEL)
        print(f"model available: {model.id} ({model.display_name})")
    except anthropic.NotFoundError:
        print(f"FAIL: model {settings.LLM_MODEL} not available to this key")
        return 1
    except anthropic.AuthenticationError:
        print("FAIL: authentication rejected (check the API key)")
        return 1
    except anthropic.APIConnectionError as exc:
        print(f"FAIL: cannot reach the API ({type(exc).__name__})")
        return 1
    usage = []
    started = time.monotonic()
    try:
        text = llm.translate("Machine romba heat aguthu, production output kammiya irukku.",
                             "Tanglish (Tamil-English)", usage_log=usage)
    except llm.LLMUnavailable as exc:
        print(f"FAIL: structured translation failed: {exc}")
        return 1
    print(f"translation: {text!r}  ({int((time.monotonic() - started) * 1000)} ms)")
    for u in usage:
        print(f"usage: {u['input_tokens']} in / {u['output_tokens']} out tokens, est ${u['estimated_cost_usd']}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
