#!/usr/bin/env python3
"""pytest suite for the independent log parser fixtures.

Validates JSONLogParser / TextLogParser / NginxLogParser from
tools/log_aggregator.py against the hand-written fixtures in
tools/log_parser_fixtures.py. Malformed lines must not crash the
parsers: expect None or a graceful entry.
"""
import sys
from pathlib import Path

import pytest

try:
    import locale
    # %b 月份缩写需英文 locale；非英文环境下防御，免得 strptime 认不出 "Jan"
    locale.setlocale(locale.LC_TIME, "C")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser
from log_parser_fixtures import JSON_LINES, TEXT_LINES, NGINX_LINES

json_parser = JSONLogParser()
text_parser = TextLogParser()
nginx_parser = NginxLogParser()


def test_json_standard_fields():
    e = json_parser.parse(JSON_LINES[0])
    assert e is not None
    # JSON 时间戳统一转 epoch int（与 text/nginx 一致），修掉了 _parse_line 的 TypeError crash
    assert e["timestamp"] == 1705329121  # 2024-01-15T14:32:01Z
    assert e["level"] == "ERROR"
    assert e["service"] == "auth"
    assert e["format"] == "json"
    assert "login failed" in e["message"]


def test_json_alternate_key_names():
    e = json_parser.parse(JSON_LINES[1])
    assert e is not None
    assert e["timestamp"] == 1705329182  # 2024-01-15T14:33:02Z
    assert e["level"] == "WARN"
    assert e["service"] == "payments"

def test_json_elastic_style_keys():
    e = json_parser.parse(JSON_LINES[2])
    assert e is not None
    assert e["level"] == "info"
    assert e["service"] == "api-gw"
    assert e["format"] == "json"


def test_json_malformed_returns_none():
    assert json_parser.parse(JSON_LINES[3]) is None


def test_text_standard_line():
    e = text_parser.parse(TEXT_LINES[0])
    assert e is not None
    assert e["timestamp"] == 1705329121  # 2024-01-15T14:32:01Z
    assert e["level"] == "error"
    assert e["service"] == "auth"
    assert e["format"] == "text"


def test_text_syslog_drift():
    e = text_parser.parse(TEXT_LINES[1])
    assert e is not None
    assert e["level"] == "warn"
    # NOTE: year-less syslog dates parse with year 1900 -> negative epoch.
    # Documenting current behavior here, not endorsing it.
    assert isinstance(e["timestamp"], int)


def test_text_iso_with_millis():
    e = text_parser.parse(TEXT_LINES[2])
    assert e is not None
    assert e["timestamp"] == 1705329121
    assert e["level"] == "info"
    assert e["service"] == "api"


def test_text_empty_line_returns_none():
    assert text_parser.parse(TEXT_LINES[3]) is None

def test_nginx_standard_line():
    e = nginx_parser.parse(NGINX_LINES[0])
    assert e is not None
    assert e["timestamp"] == 1705329121
    assert e["level"] == "info"
    assert e["service"] == "nginx"
    assert e["format"] == "nginx"
    assert e["fields"]["status"] == 200
    assert e["fields"]["remote_addr"] == "203.0.113.10"
    assert e["fields"]["user_agent"] == "Mozilla/5.0"


def test_nginx_5xx_maps_to_error():
    e = nginx_parser.parse(NGINX_LINES[1])
    assert e is not None
    assert e["fields"]["status"] == 503
    assert e["level"] == "error"


def test_nginx_missing_timezone_is_graceful():
    e = nginx_parser.parse(NGINX_LINES[2])
    assert e is not None  # no crash; entry still usable
    assert e["timestamp"] is None
    assert e["fields"]["status"] == 200


def test_nginx_garbage_returns_none():
    assert nginx_parser.parse(NGINX_LINES[3]) is None


@pytest.mark.parametrize("parser,lines", [
    (json_parser, JSON_LINES),
    (text_parser, TEXT_LINES),
    (nginx_parser, NGINX_LINES),
])
def test_no_fixture_line_crashes_parser(parser, lines):
    for line in lines:
        parser.parse(line)  # must not raise


# ---- 集成层：走 LogAggregator 全链路（单体全绿掩盖的 bug 都在这里） ----

def _aggregator():
    from log_aggregator import LogAggregator
    return LogAggregator()


def test_aggregator_routes_nginx_to_nginx_parser():
    agg = _aggregator()
    assert agg._parse_line(NGINX_LINES[0]) is True
    assert agg.entries[-1]["format"] == "nginx"  # 排序修好前这里是 "text"


def test_aggregator_json_line_no_crash_and_bucketed():
    agg = _aggregator()
    assert agg._parse_line(JSON_LINES[0]) is True  # 修好前抛 TypeError
    assert agg.entries[-1]["timestamp"] == 1705329121
    assert sum(agg.hourly_counts.values()) >= 1


def test_nginx_remote_user_field():
    e = nginx_parser.parse(NGINX_LINES[0])
    assert e["fields"]["remote_user"] == "frank"  # 修好前是 "-"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
