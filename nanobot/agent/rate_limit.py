"""In-memory sliding window rate limiter."""

import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    """Sliding window rate limiter keyed by sender_id.

    Tracks timestamps of recent requests per sender and rejects
    requests that exceed the configured per-minute or per-hour limits.
    """

    def __init__(
        self,
        max_per_minute: int = 10,
        max_per_hour: int = 100,
    ):
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self._timestamps: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, sender_id: str) -> tuple[bool, int]:
        """Check if a request from *sender_id* is allowed.

        Returns:
            (allowed, retry_after_seconds).
            If allowed is True, retry_after is 0.
            If allowed is False, retry_after is the number of seconds
            until the sender can send again.
        """
        now = time.monotonic()
        one_minute_ago = now - 60
        one_hour_ago = now - 3600

        with self._lock:
            ts = self._timestamps[sender_id]

            # Prune entries older than 1 hour
            ts[:] = [t for t in ts if t > one_hour_ago]

            recent_minute = [t for t in ts if t > one_minute_ago]

            if len(recent_minute) >= self.max_per_minute:
                oldest_in_window = min(recent_minute)
                retry_after = int(oldest_in_window - one_minute_ago) + 1
                return False, max(retry_after, 1)

            if len(ts) >= self.max_per_hour:
                oldest_in_window = min(ts)
                retry_after = int(oldest_in_window - one_hour_ago) + 1
                return False, max(retry_after, 1)

            ts.append(now)
            return True, 0
