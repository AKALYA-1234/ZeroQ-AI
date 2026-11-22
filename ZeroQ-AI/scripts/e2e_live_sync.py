#!/usr/bin/env python3
"""
Browser end-to-end check of the complaint → AI analysis → admin resolution → live customer update flow.

  python scripts/e2e_live_sync.py --base http://localhost:5173

Scenarios (each reports PASS/FAIL and timings):
  1. Customer submits a Tanglish complaint; the Track page shows the AI understanding live (no reload).
  2. Admin resolves it; the open Track page shows the resolution live (WebSocket delivery latency).
  3. Missed update: the customer's browser goes offline, the admin resolves a second complaint
     meanwhile, the browser comes back — the page re-syncs and shows the resolution without a reload.
Uses the demo accounts unless E2E_* env vars are set. Exits non-zero on any failure.
"""
import argparse
import json
import os
import sys
import time

import httpx
from playwright.sync_api import sync_playwright

TANGLISH = "Machine romba heat aguthu, production output kammiya irukku."
TIMEOUT_MS = 30_000
OFFLINE_SECONDS = 6


def api_login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()


def submit(client, token, product_id, description):
    r = client.post("/api/complaints/", headers={"Authorization": f"Bearer {token}"},
                    data={"product_id": str(product_id), "title": "E2E line issue", "description": description})
    r.raise_for_status()
    return r.json()["complaint_id"]


def resolve(client, token, cid, explanation):
    h = {"Authorization": f"Bearer {token}"}
    version = client.get(f"/api/admin/intelligence/incidents/{cid}", headers=h).json()["version"]
    r = client.post(f"/api/admin/intelligence/incidents/{cid}/resolve", headers=h, json={
        "verified_category": "Machine / Equipment Abnormality", "verified_subcategory": "Machine Overheating",
        "confirmed_root_cause": "Blocked cooling fan", "resolution_action": "Replaced the cooling fan",
        "admin_explanation": explanation, "units_contained": 0, "expected_version": version})
    r.raise_for_status()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:5173")
    args = ap.parse_args()
    results = []

    def record(name, ok, **info):
        results.append({"scenario": name, "ok": ok, **info})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {json.dumps(info)}")

    with httpx.Client(base_url=args.base, timeout=30) as client, sync_playwright() as p:
        cust = api_login(client, os.environ.get("E2E_CUSTOMER_EMAIL", "demo@customer.com"),
                         os.environ.get("E2E_CUSTOMER_PASSWORD", "DemoCustomer2024!"))
        admin = api_login(client, os.environ.get("E2E_ADMIN_EMAIL", "admin@zeroq.com"),
                          os.environ.get("E2E_ADMIN_PASSWORD", "AdminZeroQ2024!"))
        product_id = client.get("/api/products/").json()[0]["id"]

        browser = p.chromium.launch(executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_PATH") or None)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        user = {"id": cust["user_id"], "email": cust["email"], "role": cust["role"], "full_name": cust["full_name"]}
        ctx.add_init_script(f"localStorage.setItem('zeroq_token', {json.dumps(cust['access_token'])});"
                            f"localStorage.setItem('zeroq_user', {json.dumps(json.dumps(user))});")
        page = ctx.new_page()
        console_errors = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        # 1. submit + open the track page immediately; AI understanding must appear without reload
        cid = submit(client, cust["access_token"], product_id, TANGLISH)
        page.goto(f"{args.base}/customer/track-complaint/{cid}")
        page.get_by_text("Live — updates appear automatically").wait_for(timeout=TIMEOUT_MS)
        t0 = time.monotonic()
        try:
            page.get_by_text("Tanglish (Tamil-English)").wait_for(timeout=TIMEOUT_MS)
            record("ai understanding appears live", True, complaint=cid,
                   seconds_after_page_live=round(time.monotonic() - t0, 2))
        except Exception as exc:
            record("ai understanding appears live", False, error=str(exc)[:120])

        # 2. admin resolves; open page updates live
        t0 = time.monotonic()
        resolve(client, admin["access_token"], cid, "The oven motor fan was blocked; we replaced it.")
        t_resolved = time.monotonic()
        try:
            page.get_by_text("Resolved — here is what happened").wait_for(timeout=TIMEOUT_MS)
            record("resolution appears live without reload", True,
                   delivery_ms=round((time.monotonic() - t_resolved) * 1000),
                   resolve_api_ms=round((t_resolved - t0) * 1000))
        except Exception as exc:
            record("resolution appears live without reload", False, error=str(exc)[:120])

        # 3. missed update while offline → re-sync on reconnect
        cid2 = submit(client, cust["access_token"], product_id, TANGLISH)
        page.goto(f"{args.base}/customer/track-complaint/{cid2}")
        page.get_by_text("Live — updates appear automatically").wait_for(timeout=TIMEOUT_MS)
        page.get_by_text("Tanglish (Tamil-English)").wait_for(timeout=TIMEOUT_MS)
        t_off = time.monotonic()
        ctx.set_offline(True)
        page.get_by_text("Reconnecting for live updates").wait_for(timeout=TIMEOUT_MS)
        record("offline shown to customer promptly", time.monotonic() - t_off < 5,
               seconds_to_show_offline=round(time.monotonic() - t_off, 2))
        resolve(client, admin["access_token"], cid2, "Resolved while you were offline.")
        time.sleep(OFFLINE_SECONDS)
        ctx.set_offline(False)
        t0 = time.monotonic()
        try:
            page.get_by_text("Resolved — here is what happened").wait_for(timeout=TIMEOUT_MS)
            record("missed update recovered after reconnect", True, complaint=cid2,
                   seconds_after_online=round(time.monotonic() - t0, 2))
        except Exception as exc:
            record("missed update recovered after reconnect", False, error=str(exc)[:120])

        non_ws = [e for e in console_errors if "WebSocket" not in e and "ERR_INTERNET_DISCONNECTED" not in e]
        record("no unexpected console errors", not non_ws, errors=non_ws[:3])
        browser.close()

    sys.exit(0 if all(r["ok"] for r in results) else 1)


if __name__ == "__main__":
    main()
