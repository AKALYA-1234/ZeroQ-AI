"""
Fixed-window rate limiting.

Backend: Redis (INCR + EXPIRE) when REDIS_URL is set, so limits hold across
workers; otherwise an in-process store (correct for a single worker).
Limits are module attributes `(max_events, window_seconds)` so they can be tuned
in one place (and patched in tests).
"""
import logging
import threading
import time
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request

from app.core.config import settings

logger = logging.getLogger(__name__)

LOGIN_FAILURE_LIMIT: Tuple[int, int] = (10, 300)      # failed logins per (ip, email) per 5 min
REGISTER_LIMIT: Tuple[int, int] = (5, 3600)           # registrations per ip per hour
SUBMIT_LIMIT: Tuple[int, int] = (20, 3600)            # complaint submissions per user per hour
ADMIN_AI_LIMIT: Tuple[int, int] = (60, 60)            # manual analyses / previews / retrains per admin per minute
FEEDBACK_LIMIT: Tuple[int, int] = (20, 3600)          # feedback posts per user per hour

_lock = threading.Lock()
_memory: Dict[str, Tuple[int, float]] = {}
_redis = None


def _redis_client():
    global _redis
    if _redis is None and settings.REDIS_URL:
        import redis
        _redis = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1.0)
    return _redis


def _window_key(key: str, window: int) -> Tuple[str, float]:
    bucket = int(time.time() // window)
    return f"rl:{key}:{bucket}", (bucket + 1) * window


def _peek(key: str, limit: Tuple[int, int]) -> Tuple[int, float]:
    _, window = limit
    wkey, reset_at = _window_key(key, window)
    client = _redis_client()
    if client is not None:
        try:
            return int(client.get(wkey) or 0), reset_at
        except Exception as exc:  # Redis outage: fail open for counting, log loudly
            logger.error("Rate-limit Redis read failed: %s", exc)
            return 0, reset_at
    with _lock:
        count, _ = _memory.get(wkey, (0, reset_at))
        return count, reset_at


def _incr(key: str, limit: Tuple[int, int]) -> int:
    _, window = limit
    wkey, reset_at = _window_key(key, window)
    client = _redis_client()
    if client is not None:
        try:
            pipe = client.pipeline()
            pipe.incr(wkey)
            pipe.expire(wkey, window + 1)
            return int(pipe.execute()[0])
        except Exception as exc:
            logger.error("Rate-limit Redis write failed: %s", exc)
            return 0
    with _lock:
        count, _ = _memory.get(wkey, (0, reset_at))
        _memory[wkey] = (count + 1, reset_at)
        if len(_memory) > 50_000:  # drop expired buckets
            now = time.time()
            for k in [k for k, (_, r) in _memory.items() if r < now]:
                _memory.pop(k, None)
        return count + 1


def _too_many(reset_at: float) -> HTTPException:
    retry = max(1, int(reset_at - time.time()))
    return HTTPException(status_code=429, detail="Too many requests. Please try again later.",
                         headers={"Retry-After": str(retry)})


def hit(key: str, limit: Tuple[int, int]) -> None:
    """Count one event; raise 429 if it exceeds the limit."""
    count = _incr(key, limit)
    if count > limit[0]:
        _, reset_at = _peek(key, limit)
        raise _too_many(reset_at)


def ensure_below(key: str, limit: Tuple[int, int]) -> None:
    """Raise 429 if the key is already at its limit (without counting)."""
    count, reset_at = _peek(key, limit)
    if count >= limit[0]:
        raise _too_many(reset_at)


def record(key: str, limit: Tuple[int, int]) -> None:
    _incr(key, limit)


def client_ip(request: Optional[Request]) -> str:
    if request is None or request.client is None:
        return "unknown"
    return request.client.host


def reset() -> None:
    with _lock:
        _memory.clear()
