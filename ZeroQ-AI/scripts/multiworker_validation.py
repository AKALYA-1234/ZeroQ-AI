#!/usr/bin/env python3
"""
Multi-worker validation against running backends that share PostgreSQL + Redis.

  python scripts/multiworker_validation.py --workers http://127.0.0.1:8011 http://127.0.0.1:8012 \
      --redis redis://127.0.0.1:56379/0 --out multiworker_report.json

Checks (each PASS/FAIL, with timings):
  1. Cross-worker events: a customer socket on worker A receives `complaint.resolved` raised by an
     admin request handled by worker B (and vice versa); an unrelated customer receives nothing.
  2. Admin sockets on every worker receive `complaint.created` from a submission on any worker.
  3. Exactly-once delivery per socket (no duplicate event ids) across 40 submissions spread over workers.
  4. Shared rate limiting: failed logins against worker A count towards worker B's lockout.
  5. Concurrent double-resolution across workers: exactly one 200, others 409 (PostgreSQL integrity).
  6. Concurrent submissions across workers: unique complaint ids, every row persisted.
Prints no secrets.
"""
import argparse
import asyncio
import json
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx
import websockets

CUSTOMER = ("demo@customer.com", "DemoCustomer2024!")
ADMIN = ("admin@zeroq.com", "AdminZeroQ2024!")
SUBMISSIONS = 40
RESOLVE_RACES = 6
RECV_TIMEOUT_S = 8


def login(base, email, password):
    r = httpx.post(f"{base}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def register_customer(base):
    email = f"mw{uuid.uuid4().hex[:8]}@example.com"
    r = httpx.post(f"{base}/api/auth/register", timeout=30, json={
        "email": email, "password": "Multiworker2026x", "full_name": "MW Tester"})
    r.raise_for_status()
    return r.json()["access_token"]


async def open_socket(base, token):
    ws = await websockets.connect(base.replace("http", "ws", 1) + "/api/ws")
    await ws.send(json.dumps({"type": "auth", "token": token}))
    hello = json.loads(await ws.recv())
    assert hello["type"] == "connected", hello
    return ws


async def drain(ws, seconds):
    events = []
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            events.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=0.3)))
        except asyncio.TimeoutError:
            continue
    return events


def submit(base, token, product_id, text="Machine romba heat aguthu, output kammiya irukku"):
    r = httpx.post(f"{base}/api/complaints/", headers={"Authorization": f"Bearer {token}"}, timeout=60,
                   data={"product_id": str(product_id), "title": "Multiworker test", "description": text})
    r.raise_for_status()
    return r.json()["complaint_id"]


def resolve(base, token, cid, **extra):
    return httpx.post(f"{base}/api/admin/intelligence/incidents/{cid}/resolve",
                      headers={"Authorization": f"Bearer {token}"}, timeout=60, json={
                          "verified_category": "Machine / Equipment Abnormality",
                          "confirmed_root_cause": "Multiworker validation", "resolution_action": "None (test)",
                          "admin_explanation": "Resolved during multi-worker validation.", **extra}).status_code


async def scenario_events(workers, report):
    a, b = workers[0], workers[1]
    admin_tok = {i: login(w, *ADMIN) for i, w in enumerate(workers)}
    cust_tok = login(a, *CUSTOMER)
    other_tok = register_customer(a)
    product = httpx.get(f"{a}/api/products/", timeout=30).json()[0]["id"]

    # 1. customer socket on A; resolution performed via B
    cust_ws, other_ws = await open_socket(a, cust_tok), await open_socket(a, other_tok)
    # Keyed by connection index (not URL): one public URL may front several workers.
    admin_ws = {i: await open_socket(w, admin_tok[i]) for i, w in enumerate(workers)}
    cid = submit(b, cust_tok, product)                          # created on B (customer is the owner)
    created = {i: [e for e in await drain(admin_ws[i], 2) if e["type"] == "complaint.created"] for i in admin_ws}
    report["admin_sockets_receive_created_from_other_worker"] = {
        "ok": all(len(v) == 1 for v in created.values()), "per_worker": {w: len(v) for w, v in created.items()}}
    await drain(cust_ws, 3)                                      # let analysis events pass
    arrivals = []                                                # (event, server-clock latency ms)

    async def collect():
        while True:
            ev = json.loads(await cust_ws.recv())
            emitted = datetime.fromisoformat(ev["emitted_at"])
            arrivals.append((ev, (datetime.utcnow() - emitted).total_seconds() * 1000))
    collector = asyncio.create_task(collect())
    t0 = time.monotonic()
    status = resolve(b, admin_tok[1], cid)
    resolve_ms = round((time.monotonic() - t0) * 1000)
    end = time.monotonic() + RECV_TIMEOUT_S
    while time.monotonic() < end and not any(e["type"] == "complaint.resolved" for e, _ in arrivals):
        await asyncio.sleep(0.05)
    collector.cancel()
    resolved = [(e, ms) for e, ms in arrivals if e["type"] == "complaint.resolved"]
    leaked = [e for e in await drain(other_ws, 1.5) if e["payload"].get("complaint_id") == cid]
    report["cross_worker_resolution_event"] = {
        "ok": status == 200 and len(resolved) == 1 and not leaked,
        "resolve_status": status, "events_received": len(resolved), "resolve_request_ms": resolve_ms,
        "emit_to_receive_ms": round(resolved[0][1]) if resolved else None,   # worker B publish → socket on worker A
        "leaked_to_other_customer": len(leaked)}

    # reverse direction: customer socket on B, resolve via A
    cust_ws_b = await open_socket(b, cust_tok)
    cid2 = submit(a, cust_tok, product)
    await drain(cust_ws_b, 3)
    status = resolve(a, admin_tok[0], cid2)
    got = []
    end = time.monotonic() + RECV_TIMEOUT_S
    while time.monotonic() < end and not any(e["type"] == "complaint.resolved" for e in got):
        got += await drain(cust_ws_b, 0.5)
    report["cross_worker_resolution_event_reverse"] = {
        "ok": status == 200 and any(e["type"] == "complaint.resolved" for e in got), "resolve_status": status}

    # 3. exactly-once over many submissions spread across workers
    for ws in admin_ws.values():
        await drain(ws, 0.5)
    # Spread over several customers: submissions are rate limited per user (20/hour, shared via Redis).
    pool_tokens = [register_customer(a) for _ in range(3)]
    ids = []
    with ThreadPoolExecutor(8) as pool:
        ids = list(pool.map(lambda i: submit(workers[i % len(workers)], pool_tokens[i % 3], product),
                            range(SUBMISSIONS)))
    seen = {i: [e for e in await drain(admin_ws[i], 6) if e["type"] == "complaint.created"] for i in admin_ws}
    per_worker = {w: {"received": len(v), "duplicate_event_ids": len(v) - len({e["event_id"] for e in v})}
                  for w, v in seen.items()}
    report["exactly_once_delivery"] = {
        "ok": all(x["received"] == SUBMISSIONS and x["duplicate_event_ids"] == 0 for x in per_worker.values()),
        "submitted": SUBMISSIONS, "per_worker": per_worker}
    report["concurrent_submissions_unique_ids"] = {"ok": len(set(ids)) == len(ids) == SUBMISSIONS,
                                                   "submitted": len(ids), "unique": len(set(ids))}
    for ws in [cust_ws, other_ws, cust_ws_b, *admin_ws.values()]:
        await ws.close()
    return admin_tok, cust_tok, product, ids


def scenario_rate_limit(workers, report):
    a, b = workers[0], workers[1]
    email = f"lockout{uuid.uuid4().hex[:6]}@example.com"
    body = {"email": email, "password": "wrong-password1"}
    codes = []
    for i in range(12):                                          # alternate workers
        codes.append(httpx.post(f"{workers[i % 2]}/api/auth/login", json=body, timeout=30).status_code)
    report["rate_limit_shared_across_workers"] = {
        "ok": codes[0] == 401 and 429 in codes and codes.index(429) <= 11,
        "first_429_at_attempt": (codes.index(429) + 1) if 429 in codes else None,
        "note": "failures were alternated between the two workers; one worker alone saw only 6"}


def scenario_double_resolve(workers, admin_tok, cust_tok, product, report):
    outcomes = {}
    cids = [submit(workers[0], cust_tok, product) for _ in range(RESOLVE_RACES)]   # few: per-user limit
    jobs = [(cid, workers[i % len(workers)]) for cid in cids for i in range(2)]
    with ThreadPoolExecutor(len(jobs)) as pool:
        for (cid, w), code in zip(jobs, pool.map(lambda j: resolve(j[1], admin_tok[workers.index(j[1])], j[0]), jobs)):
            outcomes.setdefault(cid, []).append(code)
    report["double_resolution_across_workers"] = {
        "ok": all(sorted(v) == [200, 409] for v in outcomes.values()), "incidents": len(cids),
        "outcomes": {k: sorted(v) for k, v in outcomes.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", nargs=2, required=True,
                    help="two base URLs (two worker processes), or the same public URL twice (load balancer)")
    ap.add_argument("--out", default="multiworker_report.json")
    args = ap.parse_args()
    report = {"workers": args.workers, "started": datetime.now().astimezone().isoformat()}
    admin_tok, cust_tok, product, _ = asyncio.run(scenario_events(args.workers, report))
    scenario_rate_limit(args.workers, report)
    scenario_double_resolve(args.workers, admin_tok, cust_tok, product, report)
    checks = {k: v["ok"] for k, v in report.items() if isinstance(v, dict) and "ok" in v}
    report["summary"] = {"passed": sum(checks.values()), "total": len(checks), "checks": checks}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {json.dumps({k: v for k, v in report[name].items() if k != 'ok' and k != 'outcomes'})}")
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
