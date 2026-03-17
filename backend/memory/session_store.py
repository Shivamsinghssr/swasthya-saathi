"""
memory/session_store.py

Redis-backed multi-turn conversation memory.

Each session_id maps to a list of {role, content} dicts.
Sessions expire after SESSION_TTL seconds (default 1 hour).

Why Redis over in-memory dict:
  - Survives server restarts
  - Works across multiple workers
  - TTL-based auto-cleanup — no memory leak
  - Free tier on Railway via plugin

Fallback:
  If REDIS_URL is not set, falls back to in-memory dict silently.
  This means local dev works without Redis installed.
"""
import json
import os
import time
from typing import List, Dict, Optional

# Session TTL: 1 hour
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", 3600))

# Max messages to keep per session (prevents bloat)
MAX_MESSAGES = int(os.getenv("MAX_SESSION_MESSAGES", 20))


class SessionStore:
    """
    Redis-backed session memory with in-memory fallback.

    Usage:
        store = SessionStore()
        store.add_message("sess_123", "user", "mujhe bukhar hai")
        store.add_message("sess_123", "assistant", "Bukhar ke liye...")
        history = store.get_history("sess_123")
        # [{"role": "user", "content": "mujhe bukhar hai"},
        #  {"role": "assistant", "content": "Bukhar ke liye..."}]
    """

    def __init__(self):
        self._redis = None
        self._fallback: Dict[str, list] = {}
        self._connect()

    def _connect(self):
        redis_url = os.getenv("REDIS_URL", "")
        if not redis_url:
            print("[Memory] ℹ️  REDIS_URL not set — using in-memory fallback")
            return

        try:
            import redis
            self._redis = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            self._redis.ping()
            print("[Memory] ✅ Redis connected")
        except Exception as e:
            print(f"[Memory] ⚠️  Redis connection failed ({e}) — using in-memory fallback")
            self._redis = None

    def _key(self, session_id: str) -> str:
        return f"ss:session:{session_id}"

    def get_history(self, session_id: str) -> List[Dict]:
        """Get full conversation history for a session."""
        if self._redis:
            try:
                raw = self._redis.get(self._key(session_id))
                if raw:
                    return json.loads(raw)
                return []
            except Exception as e:
                print(f"[Memory] Redis get error: {e}")
                return self._fallback.get(session_id, [])
        return self._fallback.get(session_id, [])

    def add_message(self, session_id: str, role: str, content: str):
        """Append a message to session history."""
        history = self.get_history(session_id)
        history.append({"role": role, "content": content})

        # Trim to max messages (keep most recent)
        if len(history) > MAX_MESSAGES:
            history = history[-MAX_MESSAGES:]

        if self._redis:
            try:
                self._redis.setex(
                    self._key(session_id),
                    SESSION_TTL,
                    json.dumps(history, ensure_ascii=False)
                )
                return
            except Exception as e:
                print(f"[Memory] Redis set error: {e}")

        self._fallback[session_id] = history

    def clear_session(self, session_id: str):
        """Clear a session's history."""
        if self._redis:
            try:
                self._redis.delete(self._key(session_id))
                return
            except Exception:
                pass
        self._fallback.pop(session_id, None)

    def session_exists(self, session_id: str) -> bool:
        """Check if a session has any history."""
        return len(self.get_history(session_id)) > 0

    @property
    def backend(self) -> str:
        return "redis" if self._redis else "memory"


# Singleton — initialized once at startup
_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
