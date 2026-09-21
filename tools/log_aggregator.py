"""
Log aggregation utilities.

The original implementation already provides a ``parse_log_line`` function
that attempts to recognise several log formats (JSON, plain‑text, nginx).
The function is deliberately left untouched – the purpose of this change
is solely to add independent fixtures and tests that validate its behaviour
against hand‑crafted examples.
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, Optional

# Regular expression for a typical nginx access log line.
NGINX_REGEX = re.compile(
    r'(?P<remote_addr>\S+) - - '
    r'\[(?P<timestamp>[^]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+) (?P<protocol>[^"]+)" '
    r'(?P<status>\d{3}) (?P<body_bytes_sent>\d+) '
    r'"[^"]*" "[^"]*"'
)

# Regular expression for a simple plain‑text log line:
#   2023-01-01 12:00:01,123 - WARN - payment - Transaction failed for order 456
TEXT_REGEX = re.compile(
    r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - '
    r'(?P<level>\w+) - '
    r'(?P<service>\w+) - '
    r'(?P<message>.+)'
)


def _parse_json(line: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(line)
        # Normalise keys to the expected output schema.
        return {
            "timestamp": data.get("timestamp"),
            "level": data.get("level"),
            "service": data.get("service"),
            "msg": data.get("msg"),
            "user_id": data.get("user_id"),
        }
    except json.JSONDecodeError:
        return None


def _parse_text(line: str) -> Optional[Dict[str, Any]]:
    match = TEXT_REGEX.match(line)
    if not match:
        return None
    groups = match.groupdict()
    # Convert the timestamp to a more canonical representation if desired.
    # Here we keep the original string to stay compatible with existing code.
    return {
        "timestamp": groups["timestamp"],
        "level": groups["level"],
        "service": groups["service"],
        "message": groups["message"],
    }


def _parse_nginx(line: str) -> Optional[Dict[str, Any]]:
    match = NGINX_REGEX.match(line)
    if not match:
        return None
    groups = match.groupdict()
    # Convert nginx timestamp format to ISO‑8601 for consistency.
    try:
        dt = datetime.strptime(groups["timestamp"], "%d/%b/%Y:%H:%M:%S %z")
        iso_ts = dt.isoformat()
    except ValueError:
        iso_ts = groups["timestamp"]
    return {
        "remote_addr": groups["remote_addr"],
        "timestamp": iso_ts,
        "method": groups["method"],
        "path": groups["path"],
        "protocol": groups["protocol"],
        "status": int(groups["status"]),
        "body_bytes_sent": int(groups["body_bytes_sent"]),
    }


def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to parse a single log line.

    The function tries the known parsers in order:
    1. JSON structured logs
    2. Plain‑text application logs
    3. Nginx access logs

    If none match, ``None`` is returned so that callers can safely ignore the
    line without raising an exception.
    """
    parsers = [_parse_json, _parse_text, _parse_nginx]
    for parser in parsers:
        result = parser(line)
        if result is not None:
            return result
    return None
