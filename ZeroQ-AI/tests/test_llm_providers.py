"""Provider-agnostic LLM layer: Groq / OpenRouter adapters, failover, retries, redaction, billing.
All HTTP is mocked (httpx.MockTransport) — no network, no keys."""
import json

import httpx
import pytest

from app.core.config import settings
from app.intelligence import llm
from app.intelligence.llm_providers import OpenAICompatibleProvider
from app.intelligence.redaction import redact

from conftest import submit, incident

SECRET = "sk-test-SECRET-never-leak-123"
TRANSLATION = {"english_text": "The machine is overheating and output is low"}
ANALYSIS = {"english_translation": "Kiosk shows error 504", "issue_summary": "Kiosk software error",
            "symptoms": ["error screen"], "category": "Other / New Issue", "subcategory": "Kiosk Software Error",
            "probable_root_cause": "Kiosk backend timeout", "severity": "low", "affected_product": None,
            "recommended_resolution": "Restart kiosk service", "confidence": 0.6, "reasoning": "No similar incident"}


def completion(payload: dict, model="test-model", status=200, headers=None, finish="stop"):
    body = {"model": model, "choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 900, "completion_tokens": 120}}
    return httpx.Response(status, json=body, headers=headers or {})


def make(name, responses, model="test-model", seen=None, price=(None, None)):
    """Provider whose transport replays `responses` (Response objects or exceptions) in order."""
    queue = list(responses)

    def handler(request: httpx.Request):
        if seen is not None:
            seen.append(request)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    return OpenAICompatibleProvider(name, f"https://{name}.test/v1", SECRET, model, timeout=5, max_retries=2,
                                    retry_max_wait=10, price_in=price[0], price_out=price[1],
                                    transport=httpx.MockTransport(handler), sleep=lambda s: None)


@pytest.fixture(autouse=True)
def _reset():
    llm.reset_circuit()
    yield
    llm.set_providers(None)
    llm.set_client(None)
    llm.reset_circuit()


# ── redaction ───────────────────────────────────────────────────────────────

def test_redaction_removes_personal_data_but_keeps_operational_identifiers():
    text = ("Sarah Jenkins (sarah.j@acme-foods.com, +91 98765 43210) from Acme Foods says batch BAT000123 "
            "on line M-12 had 40 packets leaking on 2026-11-20")
    out, counts = redact(text, ["Sarah Jenkins", "Acme Foods", "sarah.j@acme-foods.com"])
    for leaked in ("Sarah", "Jenkins", "sarah.j@", "98765", "Acme"):
        assert leaked not in out
    for kept in ("BAT000123", "M-12", "40 packets", "2026-11-20"):
        assert kept in out
    assert counts == {"email": 1, "phone": 1, "customer": 2}


# ── single provider behaviour ──────────────────────────────────────────────

def test_groq_structured_success_records_provider_model_latency_tokens():
    seen = []
    llm.set_providers([make("groq", [completion(TRANSLATION, model="openai/gpt-oss-120b")], seen=seen)])
    usage = []
    text = llm.translate("Machine romba heat aguthu", "Tanglish", usage_log=usage)
    assert text.startswith("The machine")
    body = json.loads(seen[0].content)
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["name"] == "LLMTranslation"
    assert seen[0].headers["authorization"] == f"Bearer {SECRET}"
    u = usage[0]
    assert (u["provider"], u["model"], u["input_tokens"], u["output_tokens"], u["status"]) == \
        ("groq", "openai/gpt-oss-120b", 900, 120, "ok")
    assert u["latency_ms"] >= 0 and u["billing"] == "unknown" and u["estimated_cost_usd"] is None


def test_rate_limit_is_retried_honouring_retry_after():
    waits = []
    seen = []
    p = make("groq", [httpx.Response(429, headers={"retry-after": "3"}), completion(TRANSLATION)], seen=seen)
    p._sleep = waits.append
    llm.set_providers([p])
    usage = []
    llm.translate("x y z", "Tanglish", usage_log=usage)
    assert len(seen) == 2 and waits == [3.0] and usage[0]["retries"] == 1


def test_model_without_json_schema_support_retries_in_prompt_json_mode():
    seen = []
    bad = httpx.Response(400, json={"error": {"message": "response_format json_schema is not supported"}})
    llm.set_providers([make("openrouter", [bad, completion(TRANSLATION)], seen=seen)])
    usage = []
    llm.translate("x", "Hinglish", usage_log=usage)
    assert "response_format" not in json.loads(seen[1].content)
    assert usage[0]["structured_output"] == "prompt_json"


def test_free_tier_and_priced_billing_are_distinguished():
    free = make("openrouter", [completion(TRANSLATION)], model="vendor/model:free")
    paid = make("groq", [completion(TRANSLATION)], price=(0.15, 0.6))
    for provider, billing, cost in ((free, "free_tier", 0.0), (paid, "paid", round((900 * 0.15 + 120 * 0.6) / 1e6, 6))):
        llm.set_providers([provider])
        usage = []
        llm.translate("x", "Tanglish", usage_log=usage)
        assert (usage[0]["billing"], usage[0]["estimated_cost_usd"]) == (billing, cost)


# ── failover and failure handling ─────────────────────────────────────────

def test_failover_to_openrouter_when_groq_keeps_failing():
    groq = make("groq", [httpx.Response(503)] * 3)
    openrouter = make("openrouter", [completion(TRANSLATION, model="vendor/model:free")], model="vendor/model:free")
    llm.set_providers([groq, openrouter])
    usage = []
    llm.translate("x", "Tanglish", usage_log=usage)
    assert [(u["provider"], u["status"]) for u in usage] == [("groq", "error"), ("openrouter", "ok")]
    assert usage[0]["error"] == "http_503"


@pytest.mark.parametrize("failure,kind", [
    (httpx.ReadTimeout("slow"), "timeout"),
    (httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": "not json at all"}}], "usage": {}}),
     "invalid_output"),
    (httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": "{\"english_text\": \"cut"},
                                                          "finish_reason": "length"}]}), "incomplete_output"),
    (httpx.Response(401, json={"error": "bad key"}), "authentication"),
])
def test_each_failure_kind_fails_over_without_fabricating(failure, kind):
    failures = [failure] * 3 if isinstance(failure, Exception) else [failure]
    llm.set_providers([make("groq", failures), make("openrouter", [completion(TRANSLATION)])])
    usage = []
    llm.translate("x", "Tanglish", usage_log=usage)
    assert usage[0]["error"] == kind and usage[1]["provider"] == "openrouter"


def test_all_providers_failing_raises_and_never_returns_a_result():
    llm.set_providers([make("groq", [httpx.Response(500)] * 3), make("openrouter", [httpx.Response(429)] * 3)])
    with pytest.raises(llm.LLMUnavailable) as exc:
        llm.translate("x", "Tanglish")
    assert "groq:http_500" in str(exc.value) and "openrouter:rate_limited" in str(exc.value)


def test_failover_disabled_uses_only_the_primary(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FAILOVER_ENABLED", False)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    assert llm.provider_order() == ["groq"]
    monkeypatch.setattr(settings, "LLM_FAILOVER_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_FALLBACK_PROVIDERS", "openrouter,anthropic,bogus")
    assert llm.provider_order() == ["groq", "openrouter", "anthropic"]


def test_open_circuit_skips_provider_without_calling_it(monkeypatch):
    monkeypatch.setattr(settings, "LLM_CIRCUIT_FAILURES", 1)
    seen = []
    groq = make("groq", [httpx.Response(500)] * 3, seen=seen)
    llm.set_providers([groq, make("openrouter", [completion(TRANSLATION)] * 2)])
    llm.translate("x", "Tanglish")
    calls_after_first = len(seen)
    llm.translate("x", "Tanglish")             # groq circuit open → straight to openrouter
    assert len(seen) == calls_after_first
    assert llm.circuit_status()["providers"]["groq"]["state"] == "open"


# ── end to end through the engine ─────────────────────────────────────────

def test_engine_uses_provider_chain_redacts_pii_and_records_source(env):
    seen = []
    llm.set_providers([make("groq", [httpx.Response(503)] * 3),
                       make("openrouter", [completion(ANALYSIS, model="vendor/model:free")] * 3,
                            model="vendor/model:free", seen=seen)])
    cid = submit(env, "Kiosk", "The vending kiosk shows error 504. Call me on 9876543210 or mail me@corp.example")
    a = incident(env, cid)["analysis"]
    assert a["prediction_source"] == "llm"
    assert a["llm_result"]["provider"] == "openrouter" and a["llm_result"]["model"] == "vendor/model:free"
    sent = " ".join(r.content.decode() for r in seen)
    assert "9876543210" not in sent and "me@corp.example" not in sent and "cust@test.local" not in sent
    assert "[PHONE]" in sent and "[EMAIL]" in sent
    assert a["original_text"].endswith("me@corp.example")      # original preserved in our DB
    assert SECRET not in json.dumps(a)


def test_engine_falls_back_to_rules_when_every_provider_fails(env, monkeypatch):
    monkeypatch.setattr(settings, "ML_CONFIDENCE_THRESHOLD", 1.01)
    llm.set_providers([make("groq", [httpx.Response(500)] * 3), make("openrouter", [httpx.Response(500)] * 3)])
    cid = submit(env, "Line", "The conveyor machine is making a grinding noise and vibrating")
    a = incident(env, cid)["analysis"]
    assert a["prediction_source"] == "rules"
    assert "all LLM providers failed" in a["fallback_reason"]
    assert [u["status"] for u in a["llm_result"]["usage"]] == ["error", "error"]


def test_llm_status_lists_providers_without_secrets(env, monkeypatch):
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "GROQ_API_KEY", SecretStr(SECRET))
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", SecretStr(SECRET))
    monkeypatch.setattr(settings, "OPENROUTER_MODEL", "vendor/model:free")
    res = env["client"].get("/api/admin/intelligence/llm/status", headers=env["admin_h"])
    assert res.status_code == 200
    assert SECRET not in res.text
    provs = {p["provider"]: p for p in res.json()["providers"]}
    assert provs["groq"]["configured"] and provs["openrouter"]["billing"] == "free_tier"
    assert env["client"].get("/api/admin/intelligence/llm/status", headers=env["cust_h"]).status_code == 403


def test_english_working_text_is_not_replaced_by_redacted_llm_echo(env):
    """Regression: for an English complaint the LLM's (redacted) echo replaced the working text,
    so admins saw [EMAIL] instead of what the customer wrote."""
    echo = {**ANALYSIS, "english_translation": "The vending kiosk shows error 504. Mail [EMAIL]"}
    llm.set_providers([make("groq", [completion(echo)] * 2)])
    cid = submit(env, "Kiosk", "The vending kiosk shows error 504. Mail me@corp.example")
    a = incident(env, cid)["analysis"]
    assert a["prediction_source"] == "llm"
    assert "me@corp.example" in a["english_text"] and "[EMAIL]" not in a["english_text"]
