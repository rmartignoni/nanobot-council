"""Tests for the in-memory sliding window rate limiter."""

import time
from unittest.mock import patch

from nanobot.agent.rate_limit import RateLimiter


class TestRateLimiter:
    def test_allows_first_request(self):
        """First request from any sender is always allowed."""
        limiter = RateLimiter(max_per_minute=5, max_per_hour=100)
        allowed, retry_after = limiter.check("user1")
        assert allowed is True
        assert retry_after == 0

    def test_allows_within_limit(self):
        """Multiple requests within the per-minute limit are allowed."""
        limiter = RateLimiter(max_per_minute=5, max_per_hour=100)
        for _ in range(5):
            allowed, _ = limiter.check("user1")
            assert allowed is True

    def test_blocks_over_minute_limit(self):
        """Request is blocked once per-minute limit is exceeded."""
        limiter = RateLimiter(max_per_minute=3, max_per_hour=100)
        for _ in range(3):
            limiter.check("user1")

        allowed, retry_after = limiter.check("user1")
        assert allowed is False

    def test_blocks_over_hour_limit(self):
        """Request is blocked once per-hour limit is exceeded."""
        limiter = RateLimiter(max_per_minute=100, max_per_hour=5)
        # Spread requests across different "minutes" to avoid minute limit
        base_time = 1000.0
        for i in range(5):
            with patch("nanobot.agent.rate_limit.time") as mock_time:
                mock_time.monotonic.return_value = base_time + i * 61  # each 61s apart
                limiter.check("user1")

        # Now check at a time within the hour window of the first request
        with patch("nanobot.agent.rate_limit.time") as mock_time:
            mock_time.monotonic.return_value = base_time + 5 * 61
            allowed, retry_after = limiter.check("user1")
            assert allowed is False

    def test_returns_retry_after(self):
        """retry_after is positive when request is blocked."""
        limiter = RateLimiter(max_per_minute=2, max_per_hour=100)
        limiter.check("user1")
        limiter.check("user1")

        allowed, retry_after = limiter.check("user1")
        assert allowed is False
        assert retry_after > 0

    def test_different_senders_independent(self):
        """Rate limits are tracked independently per sender."""
        limiter = RateLimiter(max_per_minute=2, max_per_hour=100)
        limiter.check("user1")
        limiter.check("user1")

        # user1 is at the limit
        allowed_user1, _ = limiter.check("user1")
        assert allowed_user1 is False

        # user2 is still fresh
        allowed_user2, _ = limiter.check("user2")
        assert allowed_user2 is True

    def test_window_slides(self):
        """After 60s, the minute window slides and requests are allowed again."""
        limiter = RateLimiter(max_per_minute=2, max_per_hour=100)

        # Fill up the minute limit at time T
        base_time = 1000.0
        limiter._timestamps["user1"] = [base_time, base_time + 0.1]

        # At T+30s, still blocked
        with patch("nanobot.agent.rate_limit.time") as mock_time:
            mock_time.monotonic.return_value = base_time + 30
            allowed, _ = limiter.check("user1")
            assert allowed is False

        # Reset timestamps (the blocked check above added nothing)
        limiter._timestamps["user1"] = [base_time, base_time + 0.1]

        # At T+61s, the old timestamps fall outside the 60s window
        with patch("nanobot.agent.rate_limit.time") as mock_time:
            mock_time.monotonic.return_value = base_time + 61
            allowed, retry_after = limiter.check("user1")
            assert allowed is True
            assert retry_after == 0
