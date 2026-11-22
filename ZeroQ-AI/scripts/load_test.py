#!/usr/bin/env python3
"""
Load / concurrency test against a running backend (use a scratch database!).

  DATABASE_URL=sqlite:///<copy>.db python scripts/load_test.py --base http://127.0.0.1:8010 --create-users

Measures: concurrent complaint submissions, background AI-analysis completion, WebSocket fan-out
to many dashboards (delivery latency), concurrent analytics queries, concurrent double-resolution
integrity, and backend process memory/CPU. Results are printed and written to --out as JSON.
"""
import argparse
import asyncio
import json
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx
import psutil
import websockets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

LOAD_USERS = 10
SUBMISSIONS_PER_USER = 5
SUBMIT_CONCURRENCY = 10
WS_CLIENTS = 100
KPI_REQUESTS = 40
KPI_CONCURRENCY = 10
RACE_INCIDENTS = 10
ANALYSIS_TIMEOUT_S = 180
PASSWORD = "LoadTest2026pass"
TEXTS = ["Machine romba heat aguthu, production output kammiya irukku.", "पैकेट में कीड़े मिले",
         "The ketchup bottle leaked all over the bag", "Biscuits ellam odanji pochu", "Pouch arrived unsealed"]


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    return round(s[min(len(s) - 1, int(q * len(s)))], 1)


def summary(ms):
    return {"n": len(ms), "p50_ms": pct(ms, 0.5), "p95_ms": pct(ms, 0.95), "max_ms": round(max(ms), 1) if ms else None}


def create_users():
    from app.core.security import get_password_hash
    from app.database.connection import SessionLocal
    from app.models.user import User
    db = SessionLocal()
    try:
        hashed = get_password_hash(PASSWORD)
        for i in range(LOAD_USERS):
            email = f"load{i}@example.com"
            if not db.query(User).filter(User.email == email).first():
                db.add(User(email=email, hashed_password=hashed, role="customer"))
        db.commit()
    finally:
        db.close()


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def backend_process(port):
    for c in psutil.net_connections(kind="tcp"):
        if c.laddr and c.laddr.port == port and c.status == psutil.CONN_LISTEN and c.pid:
            return psutil.Process(c.pid)
    return None


class ResourceSampler(threading.Thread):
    def __init__(self, proc):
        super().__init__(daemon=True)
        self.proc, self.samples, self.stop = proc, [], threading.Event()

    def run(self):
        if not self.proc:
            return
        self.proc.cpu_percent(None)
        while not self.stop.is_set():
            try:
                self.samples.append((self.proc.memory_info().rss / 2**20, self.proc.cpu_percent(None)))
            except psutil.Error:
                return
            self.stop.wait(0.5)


async def ws_clients(base_ws, token, n, ready, results, done):
    async def one(i):
        async with websockets.connect(f"{base_ws}/api/ws") as ws:
            await ws.send(json.dumps({"type": "auth", "token": token}))
            json.loads(await ws.recv())
            ready.append(i)
            while not done.is_set():
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
                except asyncio.TimeoutError:
                    continue
                if msg.get("type") == "complaint.created":
                    emitted = datetime.fromisoformat(msg["emitted_at"])
                    results.append((datetime.utcnow() - emitted).total_seconds() * 1000)
    await asyncio.gather(*(one(i) for i in range(n)), return_exceptions=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8010")
    ap.add_argument("--create-users", action="store_true")
    ap.add_argument("--out", default="load_test_results.json")
    args = ap.parse_args()
    if args.create_users:
        create_users()
    port = int(args.base.rsplit(":", 1)[1])
    report = {}
    sampler = ResourceSampler(backend_process(port))
    sampler.start()

    with httpx.Client(base_url=args.base, timeout=60) as client:
        admin = login(client, "admin@zeroq.com", "AdminZeroQ2024!")
        tokens = [login(client, f"load{i}@example.com", PASSWORD) for i in range(LOAD_USERS)]
        product = client.get("/api/products/").json()[0]["id"]

        # WebSocket dashboards (admins) listening while submissions happen
        ws_latency, ready, done = [], [], threading.Event()
        base_ws = args.base.replace("http", "ws", 1)
        ws_thread = threading.Thread(target=lambda: asyncio.run(
            ws_clients(base_ws, admin, WS_CLIENTS, ready, ws_latency, done)), daemon=True)
        ws_thread.start()
        deadline = time.time() + 30
        while len(ready) < WS_CLIENTS and time.time() < deadline:
            time.sleep(0.2)
        report["websocket_clients_connected"] = len(ready)

        # Concurrent submissions
        jobs = [(tokens[i % LOAD_USERS], TEXTS[i % len(TEXTS)]) for i in range(LOAD_USERS * SUBMISSIONS_PER_USER)]
        submit_ms, errors, submitted = [], [], []

        def submit(job):
            token, text = job
            t0 = time.perf_counter()
            r = client.post("/api/complaints/", headers={"Authorization": f"Bearer {token}"},
                            data={"product_id": str(product), "title": "Load test", "description": text})
            ms = (time.perf_counter() - t0) * 1000
            if r.status_code == 200:
                submit_ms.append(ms)
                submitted.append((r.json()["complaint_id"], time.time()))
            else:
                errors.append(r.status_code)

        t_start = time.perf_counter()
        with ThreadPoolExecutor(SUBMIT_CONCURRENCY) as pool:
            list(pool.map(submit, jobs))
        report["submissions"] = {**summary(submit_ms), "errors": errors,
                                 "throughput_per_s": round(len(submit_ms) / (time.perf_counter() - t_start), 1),
                                 "unique_ids": len({c for c, _ in submitted}) == len(submitted)}

        # Background analysis completion
        ah = {"Authorization": f"Bearer {admin}"}
        pending = dict(submitted)
        analysis_s, sources = [], {}
        end = time.time() + ANALYSIS_TIMEOUT_S
        while pending and time.time() < end:
            for cid, t_sub in list(pending.items()):
                a = client.get(f"/api/admin/intelligence/incidents/{cid}", headers=ah).json().get("analysis")
                if a and a.get("status") in ("completed", "failed"):
                    analysis_s.append((time.time() - t_sub) * 1000)
                    sources[a["prediction_source"]] = sources.get(a["prediction_source"], 0) + 1
                    pending.pop(cid)
            time.sleep(0.5)
        report["analysis_completion"] = {**summary(analysis_s), "not_completed": len(pending), "sources": sources}

        time.sleep(1)
        done.set()
        ws_thread.join(timeout=10)
        report["websocket_delivery"] = {**summary(ws_latency),
                                        "expected_events": WS_CLIENTS * len(submitted),
                                        "received_events": len(ws_latency)}

        # Concurrent analytics
        kpi_ms = []

        def kpi(i):
            path = "/api/admin/intelligence/kpis" if i % 2 else "/api/admin/intelligence/trends"
            t0 = time.perf_counter()
            r = client.get(path, headers=ah, params={"scope": "all"})
            if r.status_code == 200:
                kpi_ms.append((time.perf_counter() - t0) * 1000)
        with ThreadPoolExecutor(KPI_CONCURRENCY) as pool:
            list(pool.map(kpi, range(KPI_REQUESTS)))
        report["analytics_scope_all"] = summary(kpi_ms)

        # Concurrent double resolution: exactly one success per incident
        body = {"verified_category": "Packaging Defect", "confirmed_root_cause": "Load-test cause",
                "resolution_action": "Load-test action", "admin_explanation": "Resolved during load testing."}
        race_ids = [c for c, _ in submitted[:RACE_INCIDENTS]]
        outcomes = {}

        def resolve(cid):
            r = client.post(f"/api/admin/intelligence/incidents/{cid}/resolve", headers=ah, json=body)
            outcomes.setdefault(cid, []).append(r.status_code)
        with ThreadPoolExecutor(RACE_INCIDENTS * 2) as pool:
            list(pool.map(resolve, race_ids + race_ids))
        report["double_resolution"] = {
            "incidents": len(race_ids),
            "exactly_one_success_each": all(sorted(v) == [200, 409] for v in outcomes.values()),
            "outcomes": {k: sorted(v) for k, v in outcomes.items()}}

    sampler.stop.set()
    sampler.join()
    if sampler.samples:
        report["backend_resources"] = {"rss_mb_max": round(max(m for m, _ in sampler.samples), 1),
                                       "rss_mb_last": round(sampler.samples[-1][0], 1),
                                       "cpu_pct_max": max(c for _, c in sampler.samples),
                                       "cpu_pct_mean": round(statistics.mean(c for _, c in sampler.samples), 1)}
    print(json.dumps(report, indent=1))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)


if __name__ == "__main__":
    main()
