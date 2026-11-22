#!/usr/bin/env python3
"""
Pilot account management. Run against the database in DATABASE_URL.

  python scripts/pilot_accounts.py list
  python scripts/pilot_accounts.py create-admin  --email ops@acme.com --name "Ops Lead"
  python scripts/pilot_accounts.py set-password  --email ops@acme.com
  python scripts/pilot_accounts.py deactivate    --email demo@customer.com     # records are kept
  python scripts/pilot_accounts.py deactivate    --email admin@zeroq.com       # demo admin, after creating a real one
  python scripts/pilot_accounts.py mark-test     --email qa@acme.com            # its complaints -> test data

Passwords are read from the PILOT_PASSWORD environment variable or an interactive hidden prompt —
never from a command-line argument, and never printed. Deactivation is reversible (no deletes) and
refuses to remove the last active admin.
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core import accounts  # noqa: E402
from app.database.connection import SessionLocal, engine  # noqa: E402
from app.models.user import User  # noqa: E402


def read_password(confirm: bool) -> str:
    pw = os.environ.get("PILOT_PASSWORD")
    if pw:
        return pw
    pw = getpass.getpass("Password: ")
    if confirm and getpass.getpass("Repeat password: ") != pw:
        raise accounts.AccountError("passwords do not match")
    return pw


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    c = sub.add_parser("create-admin")
    c.add_argument("--email", required=True)
    c.add_argument("--name")
    c.add_argument("--role", choices=list(accounts.ADMIN_ROLES), default="admin")
    sp = sub.add_parser("set-password")
    sp.add_argument("--email", required=True)
    d = sub.add_parser("deactivate")
    d.add_argument("--email", required=True)
    mt = sub.add_parser("mark-test", help="reclassify an account's complaints as test data")
    mt.add_argument("--email", required=True)
    args = ap.parse_args()

    print(f"database: {engine.url.render_as_string(hide_password=True)}")
    db = SessionLocal()
    try:
        if args.cmd == "list":
            for u in db.query(User).order_by(User.id).all():
                print(f"  {u.id:>3}  {u.role:<16} {'active  ' if u.is_active else 'INACTIVE'}  {u.email}")
            return 0
        if args.cmd == "create-admin":
            msg = accounts.create_admin(db, args.email, read_password(True), args.name, args.role)
        elif args.cmd == "set-password":
            msg = accounts.set_password(db, args.email, read_password(True))
        elif args.cmd == "mark-test":
            msg = accounts.mark_test(db, args.email)
        else:
            msg = accounts.deactivate(db, args.email)
        print(msg)
        return 0
    except accounts.AccountError as exc:
        print(f"ERROR: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
