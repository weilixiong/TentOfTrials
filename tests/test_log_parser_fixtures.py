"""Independent log parser fixture tests for tools/log_aggregator.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tools" / "fixtures" / "log_parser"
AGGREGATOR_PATH = ROOT / "tools" / "log_aggregator.py"


def load_log_aggregator():
    spec = importlib.util.spec_from_file_location("log_aggregator", AGGREGATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["log_aggregator"] = module
    spec.loader.exec_module(module)
    return module


log_aggregator = load_log_aggregator()
JSONLogParser = log_aggregator.JSONLogParser
TextLogParser = log_aggregator.TextLogParser
NginxLogParser = log_aggregator.NginxLogParser


def _non_comment_lines(name: str) -> list[str]:
    path = FIXTURES / name
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_json_fixture_parses_timestamp_level_service_and_message():
    parser = JSONLogParser()
    parsed = [parser.parse(line) for line in _non_comment_lines("json_lines.log")]

    assert parsed[0]["format"] == "json"
    assert parsed[0]["level"] == "ERROR"
    assert parsed[0]["service"] == "payments"
    assert parsed[0]["message"] == "timeout connecting to gateway"
    assert parsed[0]["timestamp"] == "2024-03-15T10:30:00Z"

    assert parsed[1]["level"] == "warn"
    assert parsed[1]["service"] == "auth"
    assert parsed[1]["message"] == "slow login detected"


def test_text_fixture_parses_level_service_and_timestamp():
    parser = TextLogParser()
    parsed = [parser.parse(line) for line in _non_comment_lines("text_lines.log")]

    assert parsed[0]["format"] == "text"
    assert parsed[0]["level"] == "error"
    assert parsed[0]["service"] == "payments"
    assert parsed[0]["timestamp"] is not None
    assert "Connection reset" in parsed[0]["message"]

    assert parsed[1]["level"] == "warn"
    assert parsed[1]["service"] == "auth"


def test_nginx_fixture_parses_service_status_and_level():
    parser = NginxLogParser()
    parsed = [parser.parse(line) for line in _non_comment_lines("nginx_lines.log")]

    assert parsed[0]["format"] == "nginx"
    assert parsed[0]["service"] == "nginx"
    assert parsed[0]["level"] == "info"
    assert parsed[0]["fields"]["status"] == 200
    assert "GET /api/v1/orders" in parsed[0]["message"]

    assert parsed[1]["level"] == "error"
    assert parsed[1]["fields"]["status"] == 502


def test_malformed_lines_do_not_crash_parsers():
    text_parser = TextLogParser()
    json_parser = JSONLogParser()
    nginx_parser = NginxLogParser()
    for line in _non_comment_lines("malformed_lines.log"):
        assert text_parser.parse(line) is not None
        assert json_parser.parse(line) is None
        assert nginx_parser.parse(line) is None


def test_json_parser_rejects_invalid_json():
    parser = JSONLogParser()
    assert parser.parse("this is not a valid log line {{{") is None


def test_nginx_parser_rejects_non_access_log_line():
    parser = NginxLogParser()
    assert parser.parse("<<<binary garbage>>>") is None
