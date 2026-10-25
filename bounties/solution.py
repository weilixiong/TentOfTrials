# tests/parser_fixtures.py
"""
Hand‑written log line fixtures for the log_aggregator parsers.

These fixtures are deliberately independent of the parser implementation
so that they can catch regressions when the real log format drifts.
"""

import pytest


@pytest.fixture(scope="module")
def json_log_line():
    """
    A representative JSON log line.
    """
    line = (
        '{"timestamp":"2023-01-01T12:00:00Z",'
        '"level":"INFO",'
        '"msg":"User login",'
        '"user":"alice",'
        '"session_id":"abc123"}'
    )
    expected = {
        "timestamp": "2023-01-01T12:00:00Z",
        "level": "INFO",
        "msg": "User login",
        "user": "alice",
        "session_id": "abc123",
    }
    return line, expected


@pytest.fixture(scope="module")
def text_log_line():
    """
    A representative free‑form text log line.
    Format used by the legacy text parser:
        <timestamp> <level> <message> [key=value ...]
    """
    line = (
        "2023-01-01 12:00:00 INFO User login succeeded "
        "user=alice session_id=abc123 ip=10.0.0.1"
    )
    expected = {
        "timestamp": "2023-01-01 12:00:00",
        "level": "INFO",
        "msg": "User login succeeded",
        "user": "alice",
        "session_id": "abc123",
        "ip": "10.0.0.1",
    }
    return line, expected


@pytest.fixture(scope="module")
def nginx_log_line():
    """
    A representative Nginx access log line (combined log format).
    """
    line = (
        '127.0.0.1 - - [01/Jan/2023:12:00:00 +0000] '
        '"GET /index.html HTTP/1.1" 200 1024 '
        '"-" "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"'
    )
    expected = {
        "remote_addr": "127.0.0.1",
        "remote_user": "-",
        "time_local": "01/Jan/2023:12:00:00 +0000",
        "request": "GET /index.html HTTP/1.1",
        "status": "200",
        "body_bytes_sent": "1024",
        "http_referer": "-",
        "http_user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
        ),
    }
    return line, expected