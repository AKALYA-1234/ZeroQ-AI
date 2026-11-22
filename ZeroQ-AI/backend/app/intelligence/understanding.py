"""
Query understanding: language detection → English working text → symptoms and
entities. The original text is returned untouched alongside the working text.
"""
import re
from typing import Optional

from app.intelligence import llm
from app.intelligence.language import detect_language, gloss_to_english
from app.intelligence.symptoms import extract_symptoms
from app.ml.nlp_parser import PRODUCTS

BATCH_RE = re.compile(r"\b(BAT\d{6})\b", re.IGNORECASE)
QUANTITY_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(units?|packs?|packets?|pcs|pieces|kg|g|grams|cases?|boxes)\b",
                         re.IGNORECASE)


def _entities(original: str, english: str) -> dict:
    hay = f"{original}\n{english}".lower()
    entities = {}
    batch = BATCH_RE.search(original) or BATCH_RE.search(english)
    if batch:
        entities["batch_id"] = batch.group(1).upper()
    products = [p for p in PRODUCTS if p.lower() in hay]
    if not products:
        products = [p for p in PRODUCTS if any(len(w) > 4 and w in hay for w in p.lower().split())]
    if products:
        entities["products"] = products[:3]
    qty = QUANTITY_RE.findall(english or original)
    if qty:
        entities["quantities"] = [f"{n} {u}" for n, u in qty[:3]]
    return entities


def understand(text: str, allow_llm: bool = True, usage_log: Optional[list] = None,
               pii_terms: tuple = ()) -> dict:
    original = (text or "").strip()
    lang = detect_language(original)
    english: Optional[str] = None
    method = "none"
    gloss_coverage = None

    if lang.code == "en" and not lang.is_code_mixed:
        english = original
    else:
        if allow_llm and llm.is_llm_available():
            try:
                english = llm.translate(original, lang.name, usage_log=usage_log, pii_terms=pii_terms)
                method = "llm"
            except llm.LLMUnavailable:
                english = None
        if english is None:
            gloss = gloss_to_english(original, lang.code)
            gloss_coverage = gloss.coverage
            english = gloss.text or original
            method = "glossary" if gloss.matched_terms else "unavailable"

    symptoms = extract_symptoms(english)
    return {
        "original_text": original,
        "language": lang.to_dict(),
        "english_text": english,
        "translation_method": method,
        "gloss_coverage": gloss_coverage,
        "symptoms": symptoms,
        "entities": _entities(original, english),
    }
