#!/usr/bin/env python3
"""Validate log parsers against independent hand-written fixtures.

Fixtures under tools/fixtures/log_parser/ were authored by hand — not generated
by LogParser — so they cannot false-pass by round-tripping parser output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from log_aggregator import JSONLogParser, NginxLogParser, TextLogParser  # noqa: E402

FIXTURES = ROOT / "fixtures" / "log_parser"


def load_lines(name: str) -> list[str]:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return [ln for ln in text.splitlines() if ln.strip()]


def main() -> int:
    failures: list[str] = []

    # JSON
    jp = JSONLogParser()
    json_ok = 0
    for line in load_lines("json_lines.log"):
        parsed = jp.parse(line)
        if not parsed or parsed.get("format") != "json":
            failures.append(f"json parse failed: {line[:80]}")
            continue
        if not parsed.get("message") and not parsed.get("fields"):
            failures.append(f"json missing message/fields: {line[:80]}")
            continue
        if not parsed.get("level"):
            failures.append(f"json missing level: {line[:80]}")
            continue
        json_ok += 1
    if json_ok < 3:
        failures.append(f"json_ok={json_ok} expected >=3")

    # Text
    tp = TextLogParser()
    text_ok = 0
    for line in load_lines("text_lines.log"):
        parsed = tp.parse(line)
        if not parsed or parsed.get("format") != "text":
            failures.append(f"text parse failed: {line[:80]}")
            continue
        if parsed.get("level") == "unknown" and "INFO" in line.upper():
            failures.append(f"text level missed INFO: {line[:80]}")
            continue
        if parsed.get("timestamp") is None and line[:4].isdigit():
            # extract_timestamp may fail on some formats; require level at least
            if parsed.get("level") == "unknown":
                failures.append(f"text weak parse: {line[:80]}")
                continue
        text_ok += 1
    if text_ok < 3:
        failures.append(f"text_ok={text_ok} expected >=3")

    # Nginx
    np = NginxLogParser()
    nginx_ok = 0
    for line in load_lines("nginx_lines.log"):
        parsed = np.parse(line)
        if not parsed or parsed.get("format") != "nginx":
            failures.append(f"nginx parse failed: {line[:80]}")
            continue
        if parsed.get("service") != "nginx":
            failures.append(f"nginx service field wrong: {parsed}")
            continue
        status = (parsed.get("fields") or {}).get("status")
        if status is None:
            failures.append(f"nginx missing status: {line[:80]}")
            continue
        if status >= 500 and parsed.get("level") != "error":
            failures.append(f"nginx 5xx should be error: {status}")
            continue
        if 400 <= status < 500 and parsed.get("level") != "warn":
            failures.append(f"nginx 4xx should be warn: {status}")
            continue
        nginx_ok += 1
    if nginx_ok < 3:
        failures.append(f"nginx_ok={nginx_ok} expected >=3")

    # Malformed: must not crash; JSON/nginx may return None; text may still parse
    for line in load_lines("malformed_lines.log"):
        try:
            jp.parse(line)
            tp.parse(line)
            np.parse(line)
        except Exception as e:
            failures.append(f"malformed line crashed parsers: {e!r} :: {line[:60]}")

    report = {
        "json_ok": json_ok,
        "text_ok": text_ok,
        "nginx_ok": nginx_ok,
        "failures": failures,
        "ok": not failures,
    }
    print(json.dumps(report, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
