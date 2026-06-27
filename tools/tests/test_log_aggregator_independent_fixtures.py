#!/usr/bin/env python3
"""Independent parser fixtures for the legacy log aggregator.

The fixture lines in this test are hand-written representative log records, not
generated from parser output. They are intentionally small and stable so parser
regressions show up as clear assertion failures.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.log_aggregator import JSONLogParser, LogAggregator, NginxLogParser, TextLogParser


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "log_aggregator_real_world"


def fixture_line(name: str) -> str:
    return (FIXTURE_DIR / name).read_text().splitlines()[0]


class IndependentLogParserFixtureTests(unittest.TestCase):
    def test_json_fixture_maps_core_fields(self) -> None:
        entry = JSONLogParser().parse(fixture_line("json.log"))

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["format"], "json")
        self.assertEqual(entry["timestamp"], "2026-06-27T10:15:00Z")
        self.assertEqual(entry["level"], "ERROR")
        self.assertEqual(entry["service"], "orders-api")
        self.assertEqual(entry["message"], "settlement failed")
        self.assertEqual(entry["fields"]["request_id"], "req-7f3a")

    def test_text_fixture_maps_timestamp_level_service_and_raw_message(self) -> None:
        entry = TextLogParser().parse(fixture_line("text.log"))

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["format"], "text")
        self.assertEqual(entry["timestamp"], 1782555365)
        self.assertEqual(entry["level"], "warn")
        self.assertEqual(entry["service"], "billing")
        self.assertIn("invoice retry queued", entry["message"])
        self.assertEqual(entry["fields"]["raw"], entry["message"])

    def test_nginx_fixture_maps_access_log_fields(self) -> None:
        entry = NginxLogParser().parse(fixture_line("nginx.log"))

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["format"], "nginx")
        self.assertEqual(entry["timestamp"], 1782555431)
        self.assertEqual(entry["level"], "error")
        self.assertEqual(entry["service"], "nginx")
        self.assertEqual(entry["message"], "POST /api/orders HTTP/1.1")
        self.assertEqual(entry["fields"]["remote_addr"], "203.0.113.42")
        self.assertEqual(entry["fields"]["remote_user"], "mirza")
        self.assertEqual(entry["fields"]["status"], 502)
        self.assertEqual(entry["fields"]["body_bytes"], "348")

    def test_malformed_fixture_lines_do_not_crash_or_create_false_nginx_entries(self) -> None:
        aggregator = LogAggregator()

        for line in (FIXTURE_DIR / "malformed.log").read_text().splitlines():
            aggregator._parse_line(line)

        self.assertFalse(any(entry["format"] == "nginx" for entry in aggregator.entries))

    def test_aggregator_keeps_specific_nginx_parse_before_text_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            combined_path = Path(tmpdir) / "combined.log"
            combined_path.write_text(
                "\n".join(
                    [
                        fixture_line("json.log"),
                        fixture_line("text.log"),
                        fixture_line("nginx.log"),
                        "",
                    ]
                )
            )

            aggregator = LogAggregator()
            parsed_count = aggregator.process_file(str(combined_path))

        self.assertEqual(parsed_count, 3)
        formats = [entry["format"] for entry in aggregator.entries]
        self.assertEqual(formats, ["json", "text", "nginx"])
        nginx_entry = aggregator.entries[2]
        self.assertEqual(nginx_entry["service"], "nginx")
        self.assertEqual(nginx_entry["fields"]["status"], 502)
        self.assertEqual(
            aggregator.get_summary()["time_range"],
            {
                "start": "2026-06-27T10:15:00+00:00",
                "end": "2026-06-27T10:17:11+00:00",
                "duration_hours": 0.03638888888888889,
            },
        )
        self.assertEqual(
            aggregator.get_error_timeline(),
            [{"hour": "2026-06-27T10:00", "count": 2}],
        )


if __name__ == "__main__":
    unittest.main()
