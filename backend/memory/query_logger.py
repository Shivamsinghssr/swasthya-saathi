"""
memory/query_logger.py

Logs every query + response metadata to Redis for the admin dashboard.

Stores two data structures in Redis:
  1. ss:logs         — sorted set, score=timestamp, member=JSON log entry
  2. ss:tool_counts  — hash, field=tool_name, value=count
  3. ss:latencies    — list of recent latency values (last 100)

All data expires after LOG_TTL days (default 7).
Falls back to in-memory if Redis not available.
"""
import json
import os
import time
from typing import List, Dict, Optional
from datetime import datetime


LOG_TTL     = int(os.getenv("LOG_TTL_DAYS", 7)) * 86400
MAX_LOGS    = int(os.getenv("MAX_LOGS", 500))


class QueryLogger:
    """
    Logs query metadata for admin dashboard.

    Logged per query:
        - timestamp
        - session_id
        - query text
        - tools called
        - latency (seconds)
        - response length
        - success/fail
    """

    def __init__(self):
        self._redis = None
        self._fallback_logs: List[Dict] = []
        self._fallback_tools: Dict[str, int] = {}
        self._fallback_latencies: List[float] = []
        self._connect()

    def _connect(self):
        redis_url = os.getenv("REDIS_URL", "")
        if not redis_url:
            return
        try:
            import redis
            self._redis = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            self._redis.ping()
            print("[Logger] ✅ Query logger ready (Redis)")
        except Exception as e:
            print(f"[Logger] ⚠️  Redis unavailable ({e}) — logging to memory")
            self._redis = None

    def log(
        self,
        session_id: str,
        query: str,
        tools_used: List[str],
        latency_s: float,
        response_length: int,
        success: bool = True,
    ):
        """Log a single query."""
        entry = {
            "timestamp":       datetime.now().isoformat(),
            "session_id":      session_id,
            "query":           query[:200],          # truncate long queries
            "tools_used":      tools_used,
            "latency_s":       round(latency_s, 2),
            "response_length": response_length,
            "success":         success,
        }

        if self._redis:
            try:
                ts = time.time()
                # Add to sorted set (score = timestamp for time-ordered retrieval)
                self._redis.zadd("ss:logs", {json.dumps(entry, ensure_ascii=False): ts})
                # Trim to max logs
                self._redis.zremrangebyrank("ss:logs", 0, -(MAX_LOGS + 1))
                self._redis.expire("ss:logs", LOG_TTL)

                # Increment tool counters
                for tool in tools_used:
                    self._redis.hincrby("ss:tool_counts", tool, 1)
                self._redis.expire("ss:tool_counts", LOG_TTL)

                # Append latency
                self._redis.lpush("ss:latencies", str(latency_s))
                self._redis.ltrim("ss:latencies", 0, 99)   # keep last 100
                self._redis.expire("ss:latencies", LOG_TTL)
                return
            except Exception as e:
                print(f"[Logger] Redis log error: {e}")

        # Fallback
        self._fallback_logs.append(entry)
        if len(self._fallback_logs) > MAX_LOGS:
            self._fallback_logs = self._fallback_logs[-MAX_LOGS:]
        for tool in tools_used:
            self._fallback_tools[tool] = self._fallback_tools.get(tool, 0) + 1
        self._fallback_latencies.append(latency_s)
        if len(self._fallback_latencies) > 100:
            self._fallback_latencies = self._fallback_latencies[-100:]

    def get_recent_logs(self, limit: int = 50) -> List[Dict]:
        """Get most recent query logs."""
        if self._redis:
            try:
                raw = self._redis.zrevrange("ss:logs", 0, limit - 1)
                return [json.loads(r) for r in raw]
            except Exception:
                pass
        return list(reversed(self._fallback_logs[-limit:]))

    def get_tool_counts(self) -> Dict[str, int]:
        """Get tool usage counts."""
        if self._redis:
            try:
                counts = self._redis.hgetall("ss:tool_counts")
                return {k: int(v) for k, v in counts.items()}
            except Exception:
                pass
        return dict(self._fallback_tools)

    def get_avg_latency(self) -> float:
        """Get average response latency."""
        if self._redis:
            try:
                raw = self._redis.lrange("ss:latencies", 0, -1)
                if raw:
                    vals = [float(v) for v in raw]
                    return round(sum(vals) / len(vals), 2)
            except Exception:
                pass
        if self._fallback_latencies:
            return round(
                sum(self._fallback_latencies) / len(self._fallback_latencies), 2
            )
        return 0.0

    def get_total_queries(self) -> int:
        """Get total number of logged queries."""
        if self._redis:
            try:
                return int(self._redis.zcard("ss:logs"))
            except Exception:
                pass
        return len(self._fallback_logs)

    def get_stats(self) -> Dict:
        """Get all dashboard stats in one call."""
        logs        = self.get_recent_logs(50)
        tool_counts = self.get_tool_counts()
        avg_latency = self.get_avg_latency()
        total       = self.get_total_queries()

        # Top tool
        top_tool = max(tool_counts, key=tool_counts.get) if tool_counts else "none"

        # Success rate
        if logs:
            success_count = sum(1 for l in logs if l.get("success", True))
            success_rate  = round(success_count / len(logs) * 100, 1)
        else:
            success_rate = 100.0

        return {
            "total_queries":  total,
            "avg_latency_s":  avg_latency,
            "top_tool":       top_tool,
            "success_rate":   success_rate,
            "tool_counts":    tool_counts,
            "recent_logs":    logs,
            "backend":        "redis" if self._redis else "memory",
        }
    # Add this property to the QueryLogger class
    @property
    def backend(self) -> str:
        return "redis" if self._redis else "memory"

# Singleton
_logger: Optional[QueryLogger] = None


def get_query_logger() -> QueryLogger:
    global _logger
    if _logger is None:
        _logger = QueryLogger()
    return _logger
