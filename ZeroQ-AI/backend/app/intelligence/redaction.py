"""
Redaction of personal data before text is sent to an external LLM provider.

Removed: email addresses, phone-like numbers (>= 10 digits), and the complaint's own known
customer identifiers (name, organisation, email, contact). Kept on purpose: batch codes
(BAT000123), machine/line IDs (M-12, line 3), product names, dates and quantities — the
analysis needs them and they are operational, not personal.
"""
import re
from typing import Iterable, Tuple

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Candidate phone numbers: digits with optional +, spaces, dots, dashes or brackets between them.
PHONE_CANDIDATE_RE = re.compile(r"(?<![\w])\+?\(?\d[\d\s().-]{7,}\d(?![\w])")
MIN_PHONE_DIGITS = 10
MIN_NAME_PART = 4

EMAIL_TOKEN, PHONE_TOKEN, CUSTOMER_TOKEN = "[EMAIL]", "[PHONE]", "[CUSTOMER]"


def _phone_sub(match: re.Match) -> str:
    digits = sum(ch.isdigit() for ch in match.group(0))
    return PHONE_TOKEN if digits >= MIN_PHONE_DIGITS else match.group(0)


def redact(text: str, known_terms: Iterable[str] = ()) -> Tuple[str, dict]:
    """Return (redacted_text, counts). `known_terms` are this complaint's customer identifiers."""
    if not text:
        return text or "", {}
    counts = {"email": 0, "phone": 0, "customer": 0}
    out, n = EMAIL_RE.subn(EMAIL_TOKEN, text)
    counts["email"] += n
    before = out.count(PHONE_TOKEN)
    out = PHONE_CANDIDATE_RE.sub(_phone_sub, out)
    counts["phone"] += out.count(PHONE_TOKEN) - before

    terms = set()
    for term in known_terms:
        term = (term or "").strip()
        if not term or "@" in term:
            continue
        terms.add(term)
        terms.update(part for part in re.split(r"\s+", term) if len(part) >= MIN_NAME_PART)
    for term in sorted(terms, key=len, reverse=True):          # longest first: full name before parts
        out, n = re.subn(rf"(?<!\w){re.escape(term)}(?!\w)", CUSTOMER_TOKEN, out, flags=re.IGNORECASE)
        counts["customer"] += n
    return out, {k: v for k, v in counts.items() if v}
