"""Regression tests for the production-readiness security & integrity audit (C1, C2, H1-H3, M4, M7)."""
import io

import pytest
from pydantic import ValidationError

from app.core import rate_limit
from app.core.config import Settings, DEV_SECRET_KEY
from app.models.complaint import Complaint

from conftest import submit

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def _reset_limits():
    rate_limit.reset()
    yield
    rate_limit.reset()


# ── C1: customers must not read complaints they do not own ────────────────

def test_customer_cannot_read_unowned_historical_complaint(env):
    client = env["client"]
    res = client.get("/api/complaints/HIS00001", headers=env["cust_h"])
    assert res.status_code == 404
    assert "cus0001@enterprise.com" not in res.text
    assert client.get("/api/complaints/HIS00001/timeline", headers=env["cust_h"]).status_code == 404


def test_customer_cannot_read_another_customers_complaint(env):
    cid = submit(env, "Mine", "Leaking pouch")
    assert env["client"].get(f"/api/complaints/{cid}", headers=env["other_h"]).status_code == 404
    assert env["client"].get(f"/api/complaints/{cid}", headers=env["cust_h"]).status_code == 200


# ── C2: no default signing secret in production ───────────────────────────

def test_production_rejects_default_secret():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY=DEV_SECRET_KEY, _env_file=None)
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY="short", _env_file=None)
    ok = Settings(ENVIRONMENT="production", SECRET_KEY="x" * 48, _env_file=None)
    assert ok.SECRET_KEY == "x" * 48


# ── H1: rate limiting ──────────────────────────────────────────────────────

def test_login_is_rate_limited_after_repeated_failures(env):
    client = env["client"]
    body = {"email": "nobody@example.com", "password": "wrong-password1"}
    codes = [client.post("/api/auth/login", json=body).status_code for _ in range(12)]
    assert codes[0] == 401
    assert 429 in codes
    assert client.post("/api/auth/login", json=body).headers.get("retry-after")


def test_complaint_submission_is_rate_limited(env, monkeypatch):
    monkeypatch.setattr(rate_limit, "SUBMIT_LIMIT", (2, 3600))
    client = env["client"]
    data = {"product_id": str(env["ids"]["product"]), "title": "t", "description": "Leaking pouch"}
    assert client.post("/api/complaints/", data=data, headers=env["cust_h"]).status_code == 200
    assert client.post("/api/complaints/", data=data, headers=env["cust_h"]).status_code == 200
    assert client.post("/api/complaints/", data=data, headers=env["cust_h"]).status_code == 429


# ── M7: registration password policy ──────────────────────────────────────

@pytest.mark.parametrize("password", ["short1", "allletterspassword", "12345678901"])
def test_registration_rejects_weak_passwords(env, password):
    res = env["client"].post("/api/auth/register", json={
        "email": f"weak{len(password)}@example.com", "password": password, "full_name": "Weak"})
    assert res.status_code == 422


# ── H2: complaint IDs must not collide ─────────────────────────────────────

def test_complaint_id_does_not_collide_with_existing_ids(env):
    db = env["Session"]()
    try:
        nxt = db.query(Complaint).count() + 1
        db.add(Complaint(complaint_id=f"CMP{nxt:06d}", record_type="customer_submitted",
                         product_id=env["ids"]["product"], title="squatter", description="x"))
        db.commit()
    finally:
        db.close()
    a = submit(env, "First", "Leaking pouch")
    b = submit(env, "Second", "Leaking pouch")
    assert a != b and a != f"CMP{nxt:06d}"


# ── H3: attachments are private and content-checked ───────────────────────

def test_attachments_require_owner_or_admin_and_valid_content(env):
    client = env["client"]
    data = {"product_id": str(env["ids"]["product"]), "title": "Photo", "description": "Seal open"}
    files = [("files", ("photo.png", io.BytesIO(PNG_BYTES), "image/png")),
             ("files", ("fake.png", io.BytesIO(b"<script>alert(1)</script>"), "image/png"))]
    res = client.post("/api/complaints/", data=data, files=files, headers=env["cust_h"])
    assert res.status_code == 200, res.text
    assert any("fake.png" in w for w in res.json()["upload_warnings"])
    cid = res.json()["complaint_id"]
    detail = client.get(f"/api/complaints/{cid}", headers=env["cust_h"]).json()
    assert len(detail["attachments"]) == 1
    url = detail["attachments"][0]["url"]
    assert url.startswith(f"/api/complaints/{cid}/attachments/")

    assert client.get(url).status_code in (401, 403)                      # anonymous
    assert client.get(url, headers=env["other_h"]).status_code == 404      # other customer
    own = client.get(url, headers=env["cust_h"])
    assert own.status_code == 200 and own.content == PNG_BYTES
    assert own.headers["x-content-type-options"] == "nosniff"
    filename = url.rsplit("/", 1)[-1]
    assert client.get(f"/uploads/{filename}").status_code == 404           # no public mount


# ── M4: verified resolutions stay consistent ───────────────────────────────

RESOLVE_BODY = {"verified_category": "Packaging Defect", "confirmed_root_cause": "Seal jaw worn",
                "resolution_action": "Replaced seal jaw", "admin_explanation": "We replaced a worn part."}


def test_resolve_rejects_stale_version(env):
    client = env["client"]
    cid = submit(env, "Seal", "Pack seal was open")
    stale = "2000-01-01T00:00:00"
    res = client.post(f"/api/admin/intelligence/incidents/{cid}/resolve", headers=env["admin_h"],
                      json={**RESOLVE_BODY, "expected_version": stale})
    assert res.status_code == 409
    current = client.get(f"/api/admin/intelligence/incidents/{cid}", headers=env["admin_h"]).json()["version"]
    ok = client.post(f"/api/admin/intelligence/incidents/{cid}/resolve", headers=env["admin_h"],
                     json={**RESOLVE_BODY, "expected_version": current})
    assert ok.status_code == 200, ok.text


def test_legacy_update_cannot_reopen_verified_resolution(env):
    client = env["client"]
    cid = submit(env, "Seal", "Pack seal was open")
    assert client.post(f"/api/admin/intelligence/incidents/{cid}/resolve", headers=env["admin_h"],
                       json=RESOLVE_BODY).status_code == 200
    res = client.put(f"/api/admin/complaints/{cid}", headers=env["admin_h"],
                     json={"status": "under_review", "notes": "reopen"})
    assert res.status_code == 409
    view = client.get(f"/api/complaints/{cid}", headers=env["cust_h"]).json()
    assert view["status"] == "resolved"


# ── M2 / M3: database behaviour under concurrency and restarts ──────────────

def test_sqlite_connections_use_wal_and_busy_timeout(tmp_path):
    from sqlalchemy import text
    from app.database.connection import make_engine
    eng = make_engine(f"sqlite:///{tmp_path / 'wal.db'}")
    with eng.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() >= 5000
    eng.dispose()


def test_concurrent_resolutions_produce_exactly_one(env):
    """Two admins resolving the same incident at once: one 200, one 409, one resolution row."""
    import threading
    from app.models.intelligence import IncidentResolution
    cid = submit(env, "Race", "Pack seal was open")
    results = []
    barrier = threading.Barrier(2)

    def resolve():
        barrier.wait()
        r = env["client"].post(f"/api/admin/intelligence/incidents/{cid}/resolve",
                               headers=env["admin_h"], json=RESOLVE_BODY)
        results.append(r.status_code)

    threads = [threading.Thread(target=resolve) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [200, 409], results
    db = env["Session"]()
    try:
        pk = db.query(Complaint.id).filter(Complaint.complaint_id == cid).scalar()
        assert db.query(IncidentResolution).filter(IncidentResolution.complaint_id == pk).count() == 1
    finally:
        db.close()


def test_missing_analyses_are_recovered(env):
    from app.api.intelligence import recover_missing_analyses
    from app.models.intelligence import IssueAnalysis
    cid = submit(env, "Lost", "Insects inside the packet")
    db = env["Session"]()
    try:
        pk = db.query(Complaint.id).filter(Complaint.complaint_id == cid).scalar()
        db.query(IssueAnalysis).filter(IssueAnalysis.complaint_id == pk).delete()   # simulate a crash
        db.commit()
        recovered = recover_missing_analyses(db.get_bind())
        assert recovered >= 1
        assert db.query(IssueAnalysis).filter(IssueAnalysis.complaint_id == pk).count() == 1
    finally:
        db.close()


# ── JWT validation (python-jose → PyJWT migration) ────────────────────────

def test_jwt_rejects_tampered_none_alg_and_expired_tokens(env):
    import base64, json as _json
    from datetime import timedelta
    from app.core.security import create_access_token, decode_token
    good = create_access_token({"sub": "1", "role": "admin"})
    assert decode_token(good)["sub"] == "1"
    header, payload, sig = good.split(".")
    assert decode_token(f"{header}.{payload}.{sig[:-2]}xx") is None              # tampered signature
    none_header = base64.urlsafe_b64encode(_json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    assert decode_token(f"{none_header}.{payload}.") is None                     # alg=none
    expired = create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-120))   # beyond clock-skew leeway
    assert decode_token(expired) is None
    assert env["client"].get("/api/admin/intelligence/config",
                             headers={"Authorization": f"Bearer {none_header}.{payload}."}).status_code == 401


def test_migrations_widen_varchar_on_postgres_only(tmp_path):
    """Regression: fallback_reason overflowed VARCHAR(255) on PostgreSQL. The widening migration is
    a no-op on SQLite and converts VARCHAR → TEXT on PostgreSQL (run with TEST_DATABASE_URL)."""
    import os
    from sqlalchemy import create_engine, inspect, text
    from app.database.migrations import apply_additive_migrations
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'w.db'}"
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS issue_analyses_probe"))
    if eng.dialect.name != "postgresql":
        assert apply_additive_migrations(eng) == []
        return
    from app.database import migrations
    with eng.begin() as c:
        c.execute(text("CREATE TABLE issue_analyses_probe (id int, fallback_reason varchar(255))"))
    old = migrations.WIDEN_TO_TEXT
    migrations.WIDEN_TO_TEXT = [("issue_analyses_probe", "fallback_reason")]
    try:
        assert "issue_analyses_probe.fallback_reason -> TEXT" in apply_additive_migrations(eng)
        col = next(c for c in inspect(eng).get_columns("issue_analyses_probe") if c["name"] == "fallback_reason")
        assert getattr(col["type"], "length", None) is None
        assert apply_additive_migrations(eng) == []      # idempotent
    finally:
        migrations.WIDEN_TO_TEXT = old
        with eng.begin() as c:
            c.execute(text("DROP TABLE IF EXISTS issue_analyses_probe"))
        eng.dispose()


def test_empty_environment_values_are_treated_as_unset(monkeypatch):
    """Regression: compose passes unset optional values as "" which crashed numeric settings."""
    monkeypatch.setenv("IMPACT_UNIT_COST_INR", "")
    monkeypatch.setenv("OPENROUTER_MODEL", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    s = Settings(_env_file=None)
    assert s.IMPACT_UNIT_COST_INR is None and s.OPENROUTER_MODEL is None and s.GROQ_API_KEY is None
    monkeypatch.setenv("IMPACT_UNIT_COST_INR", "12.5")
    assert Settings(_env_file=None).IMPACT_UNIT_COST_INR == 12.5


# ── pilot account provisioning ─────────────────────────────────────────────

def test_account_provisioning_rules(env):
    from app.core import accounts
    from app.models.user import User
    db = env["Session"]()
    try:
        assert "created admin" in accounts.create_admin(db, "Ops@Pilot.example", "StrongPass2026x", "Ops Lead")
        with pytest.raises(accounts.AccountError):
            accounts.create_admin(db, "ops@pilot.example", "StrongPass2026x")            # duplicate (case-insensitive)
        with pytest.raises(accounts.AccountError):
            accounts.create_admin(db, "weak@pilot.example", "short1")                     # policy
        with pytest.raises(accounts.AccountError):
            accounts.create_admin(db, "x@pilot.example", "StrongPass2026x", role="customer")
        # new admin can log in
        ok = env["client"].post("/api/auth/login", json={"email": "ops@pilot.example", "password": "StrongPass2026x"})
        assert ok.status_code == 200 and ok.json()["role"] == "admin"
        # deactivate: login refused, record kept, never the last admin
        assert "records kept" in accounts.deactivate(db, "ops@pilot.example")
        assert env["client"].post("/api/auth/login", json={"email": "ops@pilot.example",
                                                           "password": "StrongPass2026x"}).status_code == 400
        assert db.query(User).filter(User.email == "ops@pilot.example").count() == 1
        with pytest.raises(accounts.AccountError, match="last active admin"):
            accounts.deactivate(db, "admin@test.local")
        # set-password takes effect: the new password is accepted (account is inactive → 400, not 401),
        # the old one is rejected (401)
        accounts.set_password(db, "ops@pilot.example", "BrandNewPass2026x")
        login = lambda pw: env["client"].post("/api/auth/login", json={"email": "ops@pilot.example", "password": pw})
        assert login("BrandNewPass2026x").status_code == 400
        assert login("StrongPass2026x").status_code == 401
    finally:
        db.close()


def test_jwt_tolerates_small_clock_skew_between_hosts():
    """Regression: a token issued by a host whose clock is a few seconds ahead was rejected
    ("not yet valid (iat)") — intermittent 401s after a VM clock step / across workers on several hosts."""
    import time
    import jwt as pyjwt
    from app.core.config import settings as s
    from app.core.security import decode_token, CLOCK_SKEW_LEEWAY_SECONDS
    now = int(time.time())
    ahead = pyjwt.encode({"sub": "1", "exp": now + 600, "iat": now + 10}, s.SECRET_KEY, algorithm=s.ALGORITHM)
    assert decode_token(ahead)["sub"] == "1"
    far = pyjwt.encode({"sub": "1", "exp": now + 600, "iat": now + CLOCK_SKEW_LEEWAY_SECONDS + 60},
                       s.SECRET_KEY, algorithm=s.ALGORITHM)
    assert decode_token(far) is None                                   # beyond tolerance: still rejected
    expired = pyjwt.encode({"sub": "1", "exp": now - CLOCK_SKEW_LEEWAY_SECONDS - 5, "iat": now - 600},
                           s.SECRET_KEY, algorithm=s.ALGORITHM)
    assert decode_token(expired) is None
