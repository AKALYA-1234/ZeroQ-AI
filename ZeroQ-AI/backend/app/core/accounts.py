"""
Account provisioning for the pilot (used by scripts/pilot_accounts.py and tests).

Each function takes a Session, changes one thing, commits, and returns a short description.
Nothing is ever deleted: accounts are deactivated, so complaints, resolutions and audit history
that reference them stay intact. Passwords are validated against the policy and never logged.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import get_password_hash, password_policy_error
from app.models.complaint import Complaint
from app.models.notification import AuditLog, CustomerProfile
from app.models.user import User

ADMIN_ROLES = ("admin", "quality_manager")


class AccountError(Exception):
    pass


def _audit(db: Session, action: str, email: str, **details) -> None:
    db.add(AuditLog(user_id=None, action=action, resource_type="user", resource_id=email, details=details))


def create_admin(db: Session, email: str, password: str, full_name: Optional[str] = None,
                 role: str = "admin") -> str:
    email = email.strip().lower()
    if role not in ADMIN_ROLES:
        raise AccountError(f"role must be one of {ADMIN_ROLES}")
    reason = password_policy_error(password)
    if reason:
        raise AccountError(reason)
    if db.query(User).filter(User.email == email).first():
        raise AccountError(f"{email} already exists (use set-password to change its password)")
    user = User(email=email, hashed_password=get_password_hash(password), role=role, is_active=True)
    db.add(user)
    db.flush()
    if full_name:
        db.add(CustomerProfile(user_id=user.id, full_name=full_name))
    _audit(db, "provision_admin", email, role=role)
    db.commit()
    return f"created {role} {email}"


def set_password(db: Session, email: str, password: str) -> str:
    reason = password_policy_error(password)
    if reason:
        raise AccountError(reason)
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        raise AccountError(f"no such user: {email}")
    user.hashed_password = get_password_hash(password)
    _audit(db, "set_password", user.email)
    db.commit()
    return f"password updated for {user.email}"


def deactivate(db: Session, email: str) -> str:
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        raise AccountError(f"no such user: {email}")
    if user.role in ADMIN_ROLES:
        remaining = db.query(User).filter(User.role.in_(ADMIN_ROLES), User.is_active.is_(True),
                                          User.id != user.id).count()
        if remaining == 0:
            raise AccountError("refusing to deactivate the last active admin")
    user.is_active = False
    _audit(db, "deactivate_user", user.email)
    db.commit()
    return f"deactivated {user.email} (records kept)"


def mark_test(db: Session, email: str) -> str:
    """Reclassify every complaint submitted by this account as test data (excluded from real-world
    metrics and training). Metadata only — no rows are deleted or otherwise changed."""
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        raise AccountError(f"no such user: {email}")
    changed = (db.query(Complaint)
               .filter(Complaint.submitted_by_user_id == user.id, Complaint.customer_id.is_(None))
               .update({"data_origin": "test"}, synchronize_session=False))
    _audit(db, "mark_test_data", user.email, complaints=changed)
    db.commit()
    return f"marked {changed} complaint(s) from {user.email} as test data"
