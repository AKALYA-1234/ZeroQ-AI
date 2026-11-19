"""
Offline language detection and domain gloss translation.

* detect_language: Unicode-script detection for native scripts, plus lexicon /
  function-word detection for romanised, code-mixed Indic text (Tanglish,
  Hinglish, ...). Latin-script European languages are told apart with small
  stopword sets.
* gloss_to_english: maps known domain terms to English and keeps English words,
  dropping function words. It is a *gloss*, not a translation — good enough for
  the issue classifier; the LLM translator is preferred when configured.
"""
import re
from dataclasses import dataclass, field
from typing import List

from app.intelligence.lexicon import (
    CONCEPTS, ROMANISED_MARKERS, SCRIPT_RANGES, LANGUAGE_NAMES, CODE_MIXED_NAMES,
    LATIN_STOPWORDS,
)

INDIC_ROMANISED = ["ta", "hi", "te", "ml", "kn"]
EXACT_MATCH_MAX_LEN = 4          # romanised forms this short must match a whole token
NATIVE_SCRIPT_MIN_SHARE = 0.2    # share of letters that makes a non-Latin script dominant
CODE_MIX_LATIN_SHARE = 0.3       # Latin share inside native-script text that counts as mixing
ROMANISED_MIN_HITS = 2           # romanised Indic markers/terms needed to call a language

_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass
class LanguageInfo:
    code: str
    name: str
    script: str
    is_code_mixed: bool
    confidence: float
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "code": self.code, "name": self.name, "script": self.script,
            "is_code_mixed": self.is_code_mixed, "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
        }


@dataclass
class Gloss:
    text: str
    matched_terms: List[str]
    unknown_tokens: List[str]
    coverage: float


def _script_of(ch: str):
    cp = ord(ch)
    for lo, hi, code, name in SCRIPT_RANGES:
        if lo <= cp <= hi:
            return code, name
    if ch.isascii() and ch.isalpha():
        return "latin", "Latin"
    if ch.isalpha():
        return "other", "Other"
    return None


def _script_counts(text: str):
    counts, names = {}, {}
    for ch in text:
        res = _script_of(ch)
        if not res:
            continue
        code, name = res
        counts[code] = counts.get(code, 0) + 1
        names[code] = name
    return counts, names


def _romanised_term_matches(token: str, form: str) -> bool:
    if len(form) <= EXACT_MATCH_MAX_LEN:
        return token == form
    return token.startswith(form)


def _romanised_hits(text_low: str, tokens: List[str]) -> dict:
    hits = {lang: [] for lang in INDIC_ROMANISED}
    for lang in INDIC_ROMANISED:
        for marker in ROMANISED_MARKERS.get(lang, []):
            if marker in tokens:
                hits[lang].append(marker)
        for _, (_, _native, roman) in CONCEPTS.items():
            for form in roman.get(lang, []):
                if " " in form:
                    if form in text_low:
                        hits[lang].append(form)
                elif any(_romanised_term_matches(t, form) for t in tokens):
                    hits[lang].append(form)
    return hits


def detect_language(text: str) -> LanguageInfo:
    text = (text or "").strip()
    if not text:
        return LanguageInfo("und", LANGUAGE_NAMES["und"], "None", False, 0.0)

    counts, names = _script_counts(text)
    letters = sum(counts.values()) or 1
    native = {k: v for k, v in counts.items() if k not in ("latin", "other")}
    if native:
        code = max(native, key=native.get)
        share = native[code] / letters
        if share >= NATIVE_SCRIPT_MIN_SHARE:
            latin_share = counts.get("latin", 0) / letters
            mixed = latin_share >= CODE_MIX_LATIN_SHARE
            return LanguageInfo(
                code, LANGUAGE_NAMES.get(code, code), names[code], mixed,
                min(1.0, 0.6 + share * 0.4),
                [f"{names[code]} script: {share:.0%} of letters"],
            )

    text_low = text.lower()
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    hits = _romanised_hits(text_low, tokens)
    best = max(INDIC_ROMANISED, key=lambda lang: len(set(hits[lang])))
    best_hits = sorted(set(hits[best]))
    if len(best_hits) >= ROMANISED_MIN_HITS:
        return LanguageInfo(
            best, CODE_MIXED_NAMES[best], "Latin (romanised)", True,
            min(0.95, 0.5 + 0.1 * len(best_hits)),
            [f"romanised {LANGUAGE_NAMES[best]} terms: {', '.join(best_hits[:6])}"],
        )

    token_set = set(tokens)
    scores = {lang: len(token_set & words) for lang, words in LATIN_STOPWORDS.items()}
    european = max(v for k, v in scores.items() if k != "en")
    if len(best_hits) == 1 and european < 2:
        return LanguageInfo(
            best, CODE_MIXED_NAMES[best], "Latin (romanised)", True, 0.55,
            [f"single romanised {LANGUAGE_NAMES[best]} term: {best_hits[0]}"],
        )
    lang = max(scores, key=scores.get)
    if scores[lang] == 0:
        lang = "en"
    confidence = 0.9 if scores[lang] >= 2 else 0.6
    return LanguageInfo(lang, LANGUAGE_NAMES[lang], "Latin", False, confidence,
                        [f"stopword matches: {scores[lang]}"])


def _native_gloss(token: str, lang: str):
    """Return (concept_key, gloss) for a native-script token, preferring `lang`."""
    for key, (gloss, native, _roman) in CONCEPTS.items():
        forms = native.get(lang, [])
        if any(f in token for f in forms):
            return key, gloss
    for key, (gloss, native, _roman) in CONCEPTS.items():
        if any(f in token for forms in native.values() for f in forms):
            return key, gloss
    return None


def _roman_gloss(token: str, lang: str):
    langs = [lang] + [l for l in INDIC_ROMANISED if l != lang]
    for code in langs:
        for key, (gloss, _native, roman) in CONCEPTS.items():
            for form in roman.get(code, []):
                if " " not in form and _romanised_term_matches(token, form):
                    return key, gloss
    return None


def gloss_to_english(text: str, lang: str) -> Gloss:
    """Gloss domain terms to English; English words are kept, function words dropped."""
    text = text or ""
    if lang == "en":
        return Gloss(text, [], [], 1.0)

    working = text.lower()
    matched: List[str] = []
    # Multi-word romanised / native phrases first ("heat aguthu", "sariya illa").
    for key, (gloss, native, roman) in CONCEPTS.items():
        phrases = [f for forms in roman.values() for f in forms if " " in f]
        phrases += [f for forms in native.values() for f in forms if " " in f]
        for phrase in phrases:
            if phrase in working:
                working = working.replace(phrase, f" {gloss} ")
                matched.append(key)

    markers = {m for ms in ROMANISED_MARKERS.values() for m in ms}
    out, unknown = [], []
    for raw in re.split(r"(\s+|[,.;:!?।]+)", working):
        if not raw or raw.isspace():
            continue
        if re.fullmatch(r"[,.;:!?।]+", raw):
            out.append(",")
            continue
        token = raw.strip()
        counts, _ = _script_counts(token)
        is_latin = counts.get("latin", 0) >= max(1, sum(counts.values()) // 2)
        if is_latin:
            hit = _roman_gloss(token, lang) if lang in INDIC_ROMANISED else None
            if hit:
                matched.append(hit[0])
                out.append(hit[1])
            elif token in markers:
                continue
            else:
                out.append(token)  # treat as English (code-mixed) word
        else:
            hit = _native_gloss(token, lang)
            if hit:
                matched.append(hit[0])
                out.append(hit[1])
            elif any(ch.isdigit() for ch in token):
                out.append(token)
            else:
                unknown.append(token)

    considered = len(matched) + len(unknown)
    coverage = (len(matched) / considered) if considered else 0.0
    glossed = re.sub(r"\s+,", ",", " ".join(out)).strip(" ,")
    return Gloss(glossed, sorted(set(matched)), unknown, round(coverage, 2))
