# tests/parser_fixtures.py
"""
Hand‑written log line fixtures for independent parser testing.

Each fixture is a tuple:
    (log_line: str, expected: dict)

The fixtures cover the three supported formats:
* JSON log lines
* Simple space‑separated text logs
* Nginx combined access logs
"""

JSON_FIXTURE = (
    # A typical JSON log line produced by many services
    '{"timestamp":"2023-01-01T12:00:00Z","level":"INFO","message":"User login","user_id":42}',
    {
        "timestamp": "2023-01-01T12:00:00Z",
        "level": "INFO",
        "message": "User login",
        "user_id": 42,
    },
)

TEXT_FIXTURE = (
    # Simple space‑separated log: "<timestamp> <level> <message>"
    "2023-01-01 12:00:00 INFO Service started successfully",
    {
        "timestamp": "2023-01-01 12:00:00",
        "level": "INFO",
        "message": "Service started successfully",
    },
)

NGINX_FIXTURE = (
    # Classic Nginx combined log format
    '127.0.0.1 - - [01/Jan/2023:12:00:00 +0000] '
    '"GET /index.html HTTP/1.1" 200 1234 '
    '"-" "Mozilla/5.0 (compatible; TestBot/1.0)"',
    {
        "remote_addr": "127.0.0.1",
        "remote_user": "-",
        "time_local": "01/Jan/2023:12:00:00 +0000",
        "request": "GET /index.html HTTP/1.1",
        "status": 200,
        "body_bytes_sent": 1234,
        "http_referer": "-",
        "http_user_agent": "Mozilla/5.0 (compatible; TestBot/1.0)",
    },
)

# Export a flat list that the test suite can iterate over
ALL_FIXTURES = [
    JSON_FIXTURE,
    TEXT_FIXTURE,
    NGINX_FIXTURE,
]