#!/usr/bin/env python3
"""
Responsive UI audit (Playwright). For each screen at 390 / 768 / 1440 px:
  * page-level horizontal overflow (document wider than the viewport) + offending elements
  * console errors and failed (>= 400) API responses
  * a full-page screenshot

  python scripts/ui_responsive_audit.py --base http://127.0.0.1:5180 --out <dir>

Credentials come from env (AUDIT_ADMIN_EMAIL/PASSWORD, AUDIT_CUSTOMER_EMAIL/PASSWORD) and default
to the documented demo accounts. Exits non-zero if any screen overflows or logs errors.
"""
import argparse
import json
import os
import sys

from playwright.sync_api import sync_playwright

WIDTHS = [390, 768, 1440]
CUSTOMER_PAGES = ["/customer/home", "/customer/submit-complaint", "/customer/track-complaint",
                  "/customer/my-complaints"]
ADMIN_PAGES = ["/admin/dashboard", "/admin/complaints", "/admin/ai-insights", "/admin/ai-prediction",
               "/admin/capa"]
SETTLE_MS = 2500

OVERFLOW_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const offenders = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    // Ignore content inside intentionally scrollable containers.
    let p = el.parentElement, clipped = false;
    while (p && p !== document.body) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === 'auto' || ox === 'scroll' || ox === 'hidden') { clipped = true; break; }
      p = p.parentElement;
    }
    if (!clipped && r.right > vw + 1) offenders.push(
      (el.tagName.toLowerCase() + '.' + (el.className && el.className.baseVal === undefined ? el.className : '')).slice(0, 90)
      + ` right=${Math.round(r.right)}`);
  }
  return { scrollWidth: document.documentElement.scrollWidth, clientWidth: vw, offenders: offenders.slice(0, 5) };
}"""


def login(context, base, email, password):
    res = context.request.post(f"{base}/api/auth/login", data={"email": email, "password": password})
    if not res.ok:
        raise SystemExit(f"login failed for {email}: {res.status}")
    d = res.json()
    user = {"id": d["user_id"], "email": d["email"], "role": d["role"], "full_name": d["full_name"]}
    context.add_init_script(
        f"localStorage.setItem('zeroq_token', {json.dumps(d['access_token'])});"
        f"localStorage.setItem('zeroq_user', {json.dumps(json.dumps(user))});")


def audit(base, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    results = []
    accounts = [
        ("customer", os.environ.get("AUDIT_CUSTOMER_EMAIL", "demo@customer.com"),
         os.environ.get("AUDIT_CUSTOMER_PASSWORD", "DemoCustomer2024!"), CUSTOMER_PAGES),
        ("admin", os.environ.get("AUDIT_ADMIN_EMAIL", "admin@zeroq.com"),
         os.environ.get("AUDIT_ADMIN_PASSWORD", "AdminZeroQ2024!"), ADMIN_PAGES),
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_PATH") or None)
        for role, email, password, pages in accounts:
            for width in WIDTHS:
                context = browser.new_context(viewport={"width": width, "height": 900})
                login(context, base, email, password)
                page = context.new_page()
                errors, failed = [], []
                page.on("console", lambda m: errors.append(m.text[:160]) if m.type == "error" else None)
                page.on("response", lambda r: failed.append(f"{r.status} {r.url[-80:]}")
                        if r.status >= 400 and "/api/" in r.url else None)
                for path in pages:
                    errors.clear(); failed.clear()
                    page.goto(f"{base}{path}", wait_until="networkidle")
                    page.wait_for_timeout(SETTLE_MS)
                    ov = page.evaluate(OVERFLOW_JS)
                    shot = os.path.join(out_dir, f"{role}{path.replace('/', '_')}_{width}.png")
                    page.screenshot(path=shot, full_page=True)
                    ws_errors = [e for e in errors if "WebSocket" in e]
                    results.append({"role": role, "path": path, "width": width,
                                    "overflow_px": ov["scrollWidth"] - ov["clientWidth"],
                                    "offenders": ov["offenders"], "console_errors": [e for e in errors if e not in ws_errors],
                                    "websocket_errors": ws_errors, "failed_api": list(failed), "screenshot": shot})
                context.close()
        browser.close()
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5173")
    ap.add_argument("--out", default="ui_audit")
    args = ap.parse_args()
    results = audit(args.base, args.out)
    bad = 0
    for r in results:
        problems = []
        if r["overflow_px"] > 0:
            problems.append(f"overflow {r['overflow_px']}px {r['offenders']}")
        if r["console_errors"]:
            problems.append(f"console {r['console_errors'][:2]}")
        if r["failed_api"]:
            problems.append(f"api {r['failed_api'][:3]}")
        bad += bool(problems)
        print(f"{'FAIL' if problems else 'ok  '} {r['role']:<8} {r['width']:>4} {r['path']:<28} {'; '.join(problems)}")
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    print(f"\n{len(results) - bad}/{len(results)} screens clean")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
