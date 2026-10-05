#!/usr/bin/env python3
"""Independent, hand-written fixtures for the log parsers in log_aggregator.py.

These lines were written BY HAND from real-world log format knowledge
(structured JSON logs, syslog/plain-text, nginx combined) -- NOT generated
from the parser code itself. That is the whole point: fixtures derived from
the parser's own regexes/field-name lists can only confirm what the parser
already assumes (the false-pass problem noted in log_aggregator.py).

Each format ships >= 3 normal lines (including realistic format drift seen
in archived logs) + 1 malformed/unsupported line. Malformed lines must not
crash the parser: expect None or a graceful entry.
"""

# -- JSON: canonical keys, alternate key names, Elastic-style, truncated --
JSON_LINES = [
    # standard structured log
    '{"timestamp": "2024-01-15T14:32:01Z", "level": "ERROR", '
    '"service": "auth", "message": "login failed for user bob"}',
    # alternate key names seen in the wild (time/severity/logger/msg)
    '{"time": "2024-01-15 14:33:02", "severity": "WARN", '
    '"logger": "payments", "msg": "retrying webhook delivery"}',
    # Elastic-style (@timestamp / lvl / app / event)
    '{"@timestamp": "2024-01-15T14:34:03.123Z", "lvl": "info", '
    '"app": "api-gw", "event": "request completed"}',
    # malformed: truncated mid-object
    '{"timestamp": "2024-01-15", "level":',
]

# -- plain text: standard, syslog drift, ISO with millis, empty line --
TEXT_LINES = [
    "2024-01-15 14:32:01 [auth] ERROR: login failed for user bob",
    # syslog format drift: no bracketed service, lowercase name
    "Jan 15 09:12:33 app-server myapp: WARN disk usage at 91%",
    # ISO-8601 with milliseconds
    "2024-01-15T14:32:01.123 INFO [api] request completed",
    # malformed: empty line
    "",
]

# -- nginx combined: 200 OK, 503 error, missing timezone drift, garbage --
NGINX_LINES = [
    '203.0.113.10 - frank [15/Jan/2024:14:32:01 +0000] '
    '"GET /api/users HTTP/1.1" 200 1234 '
    '"https://example.com/" "Mozilla/5.0"',
    # 5xx -> level must be error
    '203.0.113.11 - - [15/Jan/2024:14:33:02 +0000] '
    '"POST /api/pay HTTP/1.1" 503 0 "-" "curl/8.0"',
    # drift: timestamp without timezone -> timestamp None, entry still valid
    '203.0.113.12 - - [15/Jan/2024:14:34:03] '
    '"GET /health HTTP/1.1" 200 12 "-" "-"',
    # malformed: not a log line at all
    "this is not a log line",
]

ALL_FIXTURES = {
    "json": JSON_LINES,
    "text": TEXT_LINES,
    "nginx": NGINX_LINES,
}
