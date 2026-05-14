"""In-memory usage limits for public demo deployments."""

from __future__ import annotations

import asyncio
import os
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class UsageLimitConfig:
    enabled: bool = True
    max_message_chars: int = 8000
    max_requests_per_minute: int = 5
    max_requests_per_day: int = 100
    max_session_requests_per_day: int = 30
    max_concurrent_runs: int = 2
    max_web_search_calls_per_session: int = 3

    @classmethod
    def from_env(cls) -> "UsageLimitConfig":
        return cls(
            enabled=_env_bool("STF_LIMITS_ENABLED", True),
            max_message_chars=_env_int("STF_MAX_MESSAGE_CHARS", 8000),
            max_requests_per_minute=_env_int("STF_MAX_REQUESTS_PER_MINUTE", 5),
            max_requests_per_day=_env_int("STF_MAX_REQUESTS_PER_DAY", 100),
            max_session_requests_per_day=_env_int("STF_MAX_SESSION_REQUESTS_PER_DAY", 30),
            max_concurrent_runs=_env_int("STF_MAX_CONCURRENT_RUNS", 2),
            max_web_search_calls_per_session=_env_int("STF_MAX_WEB_SEARCH_CALLS_PER_SESSION", 3),
        )


class UsageLimitExceeded(Exception):
    """Raised when a demo usage limit is exceeded."""

    def __init__(self, message: str, status_code: int = 429) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class UsageLimiter:
    """Process-local limiter for public demo traffic.

    This is intentionally simple and dependency-free. For multi-process or multi-instance
    deployments, replace it with Redis or a managed rate-limit gateway.
    """

    def __init__(self, config: UsageLimitConfig | None = None) -> None:
        self.config = config or UsageLimitConfig.from_env()
        self._lock = asyncio.Lock()
        self._minute_requests: dict[str, deque[float]] = defaultdict(deque)
        self._daily_requests: dict[tuple[str, str], int] = defaultdict(int)
        self._session_daily_requests: dict[tuple[str, str], int] = defaultdict(int)
        self._web_search_calls: dict[tuple[str, str], int] = defaultdict(int)
        self._concurrency = asyncio.Semaphore(max(1, self.config.max_concurrent_runs))

    async def check_request(self, client_key: str, session_id: str, message_chars: int) -> None:
        if not self.config.enabled:
            return

        if message_chars > self.config.max_message_chars:
            raise UsageLimitExceeded(
                f"Message is too long. Limit is {self.config.max_message_chars} characters.",
                status_code=413,
            )

        now = monotonic()
        today = self._today()
        async with self._lock:
            minute_bucket = self._minute_requests[client_key]
            while minute_bucket and now - minute_bucket[0] >= 60:
                minute_bucket.popleft()
            if len(minute_bucket) >= self.config.max_requests_per_minute:
                raise UsageLimitExceeded(
                    f"Rate limit exceeded. Try again later. Limit is {self.config.max_requests_per_minute} requests per minute."
                )

            daily_key = (client_key, today)
            if self._daily_requests[daily_key] >= self.config.max_requests_per_day:
                raise UsageLimitExceeded(
                    f"Daily request limit exceeded. Limit is {self.config.max_requests_per_day} requests per day."
                )

            session_key = (session_id, today)
            if self._session_daily_requests[session_key] >= self.config.max_session_requests_per_day:
                raise UsageLimitExceeded(
                    f"Session request limit exceeded. Limit is {self.config.max_session_requests_per_day} requests per day."
                )

            minute_bucket.append(now)
            self._daily_requests[daily_key] += 1
            self._session_daily_requests[session_key] += 1

    async def try_acquire_run_slot(self) -> bool:
        if not self.config.enabled:
            return True
        if self._concurrency.locked():
            return False
        await self._concurrency.acquire()
        return True

    def release_run_slot(self) -> None:
        if self.config.enabled:
            self._concurrency.release()

    async def check_web_search(self, session_id: str) -> None:
        if not self.config.enabled:
            return

        today = self._today()
        key = (session_id, today)
        async with self._lock:
            if self._web_search_calls[key] >= self.config.max_web_search_calls_per_session:
                raise UsageLimitExceeded(
                    "Web search limit exceeded for this session. Try using existing database records or start a new session."
                )
            self._web_search_calls[key] += 1

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).date().isoformat()
