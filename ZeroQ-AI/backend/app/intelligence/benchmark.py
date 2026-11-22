"""Backward-compatible view of the independent evaluation set as (text, language, category) tuples."""
from app.intelligence.eval_dataset import EVAL_ITEMS

BENCHMARK = [(text, lang, category) for text, lang, category, _group in EVAL_ITEMS]
