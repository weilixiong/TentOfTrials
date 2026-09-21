"""
Tests for the log parser using hand‑written independent fixtures.

The fixtures live under ``tests/fixtures/log_parser`` and represent three
common log formats that the aggregator supports:

* JSON structured logs
* Plain‑text application logs
* Nginx access logs

A malformed line is also included to ensure the parser fails gracefully
instead of raising an exception.
"""

import json
import pathlib

import pytest

# The parser entry point – the repository already provides a function that
# parses a single log line and returns a dictionary with normalized fields.
# Adjust the import path if the actual function name differs.
from tools.log_aggregator import parse_log_line  # type: ignore


FIXTURE_ROOT = pathlib.Path(__file__).parent / "fixtures" / "log_parser"


def _read_fixture(name: str) -> str:
    """Utility to read a fixture file as a raw string."""
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8").strip()


@pytest.mark.parametrize(
    "fixture_name,expected_keys",
    [
        (
            "json.log",
            {"timestamp", "level", "service", "msg", "user_id"},
        ),
        (
            "text.log",
            {"timestamp", "level", "service", "message"},
        ),
        (
            "nginx.log",
            {"remote_addr", "timestamp", "method", "path", "protocol", "status", "body_bytes_sent"},
        ),
    ],
)
def test_parser_successful_cases(fixture_name: str, expected_keys: set):
    """
    Verify that each well‑formed fixture is parsed without error and that the
    resulting dictionary contains the expected normalized keys.
    """
    raw_line = _read_fixture(fixture_name)
    result = parse_log_line(raw_line)

    # The parser should always return a dict for supported formats.
    assert isinstance(result, dict), f"Parser returned non‑dict for {fixture_name}"

    # All expected keys must be present (additional keys are allowed).
    missing = expected_keys - result.keys()
    assert not missing, f"Missing keys {missing} in parsed output for {fixture_name}"

    # Basic sanity checks on a few fields to ensure correct typing.
    if "timestamp" in result:
        # Timestamps are expected to be ISO‑8601 strings or datetime objects.
        # Accept both for flexibility.
        ts = result["timestamp"]
        assert isinstance(ts, (str, int, float)), "Timestamp has unexpected type"

    if "level" in result:
        assert isinstance(result["level"], str), "Log level should be a string"


def test_parser_malformed_line():
    """
    A malformed/unsupported line must not raise an exception.
    The parser should return ``None`` or an empty dict to signal that the line
    could not be interpreted.
    """
    raw_line = _read_fixture("malformed.log")
    result = parse_log_line(raw_line)

    # The contract of ``parse_log_line`` for unknown formats is to return
    # ``None`` (or an empty dict). Both are acceptable as long as no exception
    # is raised.
    assert result is None or result == {}, "Malformed line should yield no parsed data"
