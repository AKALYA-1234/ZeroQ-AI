"""
Historical incident retrieval (semantic search) and evidence aggregation.

Corpus = resolved complaints joined with their investigation (root cause) and
CAPA (resolution + effectiveness), plus admin-verified platform incidents.
Texts are embedded with a locally cached sentence-transformers model when
available (EMBEDDING_BACKEND=auto|sentence-transformers), else TF-IDF.
Because many historical rows share the same template text, similarity is
computed per *distinct* text and mapped back to rows.
"""
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

TEXT_WEIGHT, SUBCATEGORY_WEIGHT, PRODUCT_WEIGHT = 0.75, 0.15, 0.10
EVIDENCE_BONUS = 0.02
EVIDENCE_POOL = 60         # neighbours used for root-cause / resolution statistics
EFFECTIVENESS_SCORE = {"effective": 1.0, "partially_effective": 0.5, "ineffective": 0.0}

_CORPUS_SQL = """
SELECT c.id, c.complaint_id, c.record_type, c.title, c.description, c.category,
       c.complaint_subcategory, c.reported_severity, c.product_id, p.name AS product_name,
       c.submitted_date, c.resolved_date,
       (SELECT i.root_cause_description FROM investigations i WHERE i.complaint_id = c.id
         ORDER BY i.is_root_cause_verified DESC, i.id LIMIT 1) AS root_cause,
       (SELECT i.is_root_cause_verified FROM investigations i WHERE i.complaint_id = c.id
         ORDER BY i.is_root_cause_verified DESC, i.id LIMIT 1) AS root_cause_verified,
       (SELECT ca.description FROM corrective_actions ca WHERE ca.complaint_id = c.id
         ORDER BY ca.id LIMIT 1) AS resolution,
       (SELECT ca.preventive_action FROM corrective_actions ca WHERE ca.complaint_id = c.id
         ORDER BY ca.id LIMIT 1) AS preventive_action,
       (SELECT ca.effectiveness_status FROM corrective_actions ca WHERE ca.complaint_id = c.id
         ORDER BY ca.id LIMIT 1) AS effectiveness,
       r.english_text AS verified_text, r.verified_category, r.verified_subcategory,
       r.confirmed_root_cause, r.resolution_action
FROM complaints c
LEFT JOIN products p ON p.id = c.product_id
LEFT JOIN incident_resolutions r ON r.complaint_id = c.id
WHERE c.status = 'resolved'
"""


@dataclass
class _Row:
    data: dict
    text_idx: int


class _Encoder:
    def __init__(self, texts: List[str]):
        self.backend = "tfidf"
        self._st = None
        if settings.EMBEDDING_BACKEND in ("auto", "sentence-transformers"):
            try:
                from sentence_transformers import SentenceTransformer
                self._st = SentenceTransformer(settings.EMBEDDING_MODEL, local_files_only=True)
                self.backend = f"sentence-transformers:{settings.EMBEDDING_MODEL}"
            except Exception as exc:  # model not cached / library missing
                logger.info("Embedding model unavailable (%s); using TF-IDF", exc)
        if self._st is None:
            self._tfidf = FeatureUnion([
                ("w", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
                ("c", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
            ]).fit([t.lower() for t in texts])
        self.matrix = self.encode(texts)

    def encode(self, texts: List[str]) -> np.ndarray:
        if self._st is not None:
            return np.asarray(self._st.encode(texts, normalize_embeddings=True))
        mat = self._tfidf.transform([t.lower() for t in texts]).toarray()
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        return mat / np.where(norms == 0, 1, norms)


class HistoricalIndex:
    def __init__(self, rows: List[dict]):
        texts, index_of = [], {}
        self.rows: List[_Row] = []
        for r in rows:
            t = (r.get("verified_text") or r.get("description") or "").strip()
            if not t:
                continue
            if t not in index_of:
                index_of[t] = len(texts)
                texts.append(t)
            self.rows.append(_Row(r, index_of[t]))
        self.texts = texts
        self.encoder = _Encoder(texts or ["empty"])

    @property
    def size(self) -> int:
        return len(self.rows)

    def search(self, query: str, subcategory: Optional[str] = None, product_id: Optional[int] = None,
               top_k: int = 8, exclude_complaint_pk: Optional[int] = None,
               category: Optional[str] = None) -> dict:
        """Rank incidents by similarity. When `category` is given, root-cause / resolution
        evidence is aggregated only over incidents of that category (unrelated incidents
        are still listed for comparison, but never become evidence)."""
        if not self.rows or not (query or "").strip():
            return {"incidents": [], "best_similarity": 0.0, "evidence": _empty_evidence(),
                    "category_matches": 0, "backend": self.encoder.backend, "corpus_size": self.size}
        q = self.encoder.encode([query])[0]
        text_sims = self.encoder.matrix @ q
        scored = []
        for row in self.rows:
            d = row.data
            if exclude_complaint_pk and d["id"] == exclude_complaint_pk:
                continue
            sim = float(text_sims[row.text_idx])
            sub = d.get("verified_subcategory") or d.get("complaint_subcategory")
            score = TEXT_WEIGHT * sim
            score += SUBCATEGORY_WEIGHT * (1.0 if subcategory and sub == subcategory else 0.0)
            score += PRODUCT_WEIGHT * (1.0 if product_id and d.get("product_id") == product_id else 0.0)
            # Small bonus for incidents that carry usable evidence.
            score += EVIDENCE_BONUS * bool(d.get("confirmed_root_cause") or d.get("root_cause"))
            score += EVIDENCE_BONUS * bool(d.get("resolution_action") or d.get("resolution"))
            scored.append((score, sim, d))
        # Ties (identical template text) → most recent first.
        scored.sort(key=lambda s: (s[0], str(s[2].get("resolved_date") or "")), reverse=True)
        best_sim = max((s[1] for s in scored), default=0.0)
        pool = scored
        if category:
            pool = [s for s in scored if (s[2].get("verified_category") or s[2].get("category")) == category]
        return {
            "incidents": [_incident_view(score, sim, d) for score, sim, d in scored[:top_k]],
            "best_similarity": round(best_sim, 4),
            "category_matches": len(pool),
            "evidence": _aggregate(pool[:EVIDENCE_POOL]),
            "backend": self.encoder.backend,
            "corpus_size": self.size,
        }


def _incident_view(score: float, sim: float, d: dict) -> dict:
    verified = d.get("verified_category") is not None
    return {
        "complaint_id": d["complaint_id"],
        "source": "platform_verified" if verified else "historical",
        "description": d.get("verified_text") or d.get("description"),
        "category": d.get("verified_category") or d.get("category"),
        "subcategory": d.get("verified_subcategory") or d.get("complaint_subcategory"),
        "severity": d.get("reported_severity"),
        "product": d.get("product_name"),
        "root_cause": d.get("confirmed_root_cause") or d.get("root_cause"),
        "root_cause_verified": bool(verified or d.get("root_cause_verified")),
        "resolution": d.get("resolution_action") or d.get("resolution"),
        "preventive_action": d.get("preventive_action"),
        "effectiveness": "admin_verified" if verified else d.get("effectiveness"),
        "submitted_date": str(d.get("submitted_date") or "")[:10] or None,
        "resolved_date": str(d.get("resolved_date") or "")[:10] or None,
        "similarity": round(sim, 4),
        "match_score": round(score, 4),
    }


def _empty_evidence() -> dict:
    return {"root_causes": [], "resolutions": [], "severity_distribution": {}, "pool_size": 0}


def _aggregate(pool) -> dict:
    if not pool:
        return _empty_evidence()
    root_w: Dict[str, float] = defaultdict(float)
    root_n: Dict[str, int] = defaultdict(int)
    sev: Dict[str, float] = defaultdict(float)
    res: Dict[str, dict] = {}
    for score, _sim, d in pool:
        rc = d.get("confirmed_root_cause") or d.get("root_cause")
        if rc:
            root_w[rc] += score
            root_n[rc] += 1
        if d.get("reported_severity"):
            sev[d["reported_severity"]] += score
        action = d.get("resolution_action") or d.get("resolution")
        if action:
            entry = res.setdefault(action, {"action": action, "preventive_action": d.get("preventive_action"),
                                            "uses": 0, "scored": 0, "score_sum": 0.0})
            entry["uses"] += 1
            eff = EFFECTIVENESS_SCORE.get(d.get("effectiveness") or "")
            if eff is not None:
                entry["scored"] += 1
                entry["score_sum"] += eff
    total_w = sum(root_w.values()) or 1.0
    root_causes = sorted(
        ({"root_cause": k, "share": round(v / total_w, 4), "incidents": root_n[k]} for k, v in root_w.items()),
        key=lambda x: -x["share"])[:5]
    resolutions = []
    for e in res.values():
        rate = (e["score_sum"] / e["scored"]) if e["scored"] else None
        resolutions.append({"action": e["action"], "preventive_action": e["preventive_action"],
                            "uses": e["uses"], "evaluated": e["scored"],
                            "success_rate": round(rate, 4) if rate is not None else None})
    resolutions.sort(key=lambda x: (x["success_rate"] or 0) * min(x["evaluated"], 10) + x["uses"] * 0.01,
                     reverse=True)
    sev_total = sum(sev.values()) or 1.0
    return {
        "root_causes": root_causes,
        "resolutions": resolutions[:5],
        "severity_distribution": {k: round(v / sev_total, 4) for k, v in sev.items()},
        "pool_size": len(pool),
    }


_index_lock = threading.Lock()
_indexes: Dict[str, HistoricalIndex] = {}


def get_index(db: Session) -> HistoricalIndex:
    key = str(db.get_bind().url)
    with _index_lock:
        if key not in _indexes:
            rows = [dict(r._mapping) for r in db.execute(sql_text(_CORPUS_SQL))]
            _indexes[key] = HistoricalIndex(rows)
            logger.info("Historical index built: %d incidents, backend=%s",
                        _indexes[key].size, _indexes[key].encoder.backend)
        return _indexes[key]


def invalidate_index() -> None:
    with _index_lock:
        _indexes.clear()
