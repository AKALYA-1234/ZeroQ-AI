"""
Data provenance. Four kinds of record must never be mixed in real-world metrics:

  synthetic  the imported historical dataset (rows carrying a dataset `customer_id`)
  real       complaints submitted by real pilot customers  <- the only basis of real-world accuracy
  test       submissions from designated test/demo accounts (PILOT_TEST_EMAILS)
  (plus)     model-generated predictions (IssueAnalysis) and admin-verified incidents
             (IncidentResolution) are layers *on top of* real complaints, never a separate origin.

Legacy rows have data_origin NULL; they are classed from `customer_id`.
"""
from typing import Optional

from app.core.config import settings

SYNTHETIC, REAL, TEST = "synthetic", "real", "test"
ORIGINS = (SYNTHETIC, REAL, TEST)

# SQL fragments over alias `c` (complaints). Constant strings, selected by a validated key.
ORIGIN_SQL = {
    "live": "c.customer_id IS NULL AND COALESCE(c.data_origin, 'real') = 'real'",
    "test": "c.customer_id IS NULL AND c.data_origin = 'test'",
    "imported": "c.customer_id IS NOT NULL",
    "all": "1 = 1",
}
# Complaints that may feed training / real-world monitoring (everything except test submissions).
NOT_TEST_SQL = "(c.data_origin IS NULL OR c.data_origin <> 'test')"


def complaint_origin(customer_id: Optional[str], data_origin: Optional[str]) -> str:
    if customer_id:
        return SYNTHETIC
    return data_origin if data_origin in (REAL, TEST) else REAL


def is_test_account(email: str) -> bool:
    """PILOT_TEST_EMAILS entries are exact addresses, or whole domains written as "@domain"."""
    email = (email or "").strip().lower()
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    for entry in settings.pilot_test_emails:
        if entry.startswith("@") and domain == entry[1:]:
            return True
        if entry == email:
            return True
    return False


def origin_for_new_submission(email: str) -> str:
    return TEST if is_test_account(email) else REAL
