"""Tests for pure / standalone functions across the codebase."""

from unittest.mock import patch

from nanobot.channels.base import split_message
from nanobot.agent.tools.web import _validate_url, _check_ssrf


# --- split_message ---


def test_split_message_short() -> None:
    result = split_message("short text")
    assert result == ["short text"]


def test_split_message_long() -> None:
    # Create a message longer than the default 4000 limit
    long_text = "word " * 1000  # 5000 chars
    chunks = split_message(long_text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 4000


def test_split_message_empty() -> None:
    assert split_message("") == []


def test_split_message_custom_max_len() -> None:
    text = "a" * 50
    chunks = split_message(text, max_len=20)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk) <= 20


# --- _validate_url ---


def test_validate_url_valid() -> None:
    ok, _ = _validate_url("https://example.com/path?q=1")
    assert ok is True


def test_validate_url_valid_http() -> None:
    ok, _ = _validate_url("http://example.com")
    assert ok is True


def test_validate_url_invalid_scheme() -> None:
    ok, err = _validate_url("ftp://example.com")
    assert ok is False
    assert "http" in err.lower() or "ftp" in err.lower()


def test_validate_url_invalid_no_domain() -> None:
    ok, err = _validate_url("https://")
    assert ok is False
    assert "domain" in err.lower() or "missing" in err.lower()


def test_validate_url_invalid_no_scheme() -> None:
    ok, err = _validate_url("not-a-url")
    assert ok is False


# --- _check_ssrf ---


def test_check_ssrf_blocks_private() -> None:
    """Private IPs (127.0.0.1, 10.x, 192.168.x) should be blocked."""
    # Mock DNS resolution to return a private IP
    fake_addr = [(2, 1, 6, "", ("127.0.0.1", 0))]
    with patch("nanobot.agent.tools.web.socket.getaddrinfo", return_value=fake_addr):
        ok, err = _check_ssrf("http://evil.example.com")
        assert ok is False
        assert "private" in err.lower() or "internal" in err.lower()


def test_check_ssrf_blocks_link_local() -> None:
    fake_addr = [(2, 1, 6, "", ("169.254.1.1", 0))]
    with patch("nanobot.agent.tools.web.socket.getaddrinfo", return_value=fake_addr):
        ok, _ = _check_ssrf("http://link-local.example.com")
        assert ok is False


def test_check_ssrf_allows_public() -> None:
    """Public IPs should be allowed."""
    fake_addr = [(2, 1, 6, "", ("93.184.216.34", 0))]
    with patch("nanobot.agent.tools.web.socket.getaddrinfo", return_value=fake_addr):
        ok, err = _check_ssrf("http://example.com")
        assert ok is True
        assert err == ""
