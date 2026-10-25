"""Independent regression fixtures for tools/log_aggregator.py."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.log_aggregator import (  # noqa: E402
    JSONLogParser,
    LogAggregator,
    NginxLogParser,
    TextLogParser,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "logs"


def fixture_lines(name: str) -> list[str]:
    return [
        line.strip()
        for line in (FIXTURE_ROOT / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class StructuredJsonFixtureTests(unittest.TestCase):
    def test_fields_are_parsed_from_independent_json_lines(self) -> None:
        parser = JSONLogParser()
        entries = [parser.parse(line) for line in fixture_lines("structured.jsonl")]

        self.assertTrue(all(entry is not None for entry in entries))
        first, second, third = entries

        self.assertEqual(first["timestamp"], 1790842530)
        self.assertEqual(first["level"], "ERROR")
        self.assertEqual(first["service"], "payments")
        self.assertEqual(first["message"], "settlement rejected")
        self.assertEqual(first["fields"]["trace_id"], "trace-a1")

        self.assertEqual(second["timestamp"], 1790842531)
        self.assertEqual(second["level"], "warn")
        self.assertEqual(second["service"], "ledger")
        self.assertEqual(second["message"], "balance drift detected")

        self.assertEqual(third["timestamp"], 1790842621)
        self.assertEqual(third["level"], "debug")
        self.assertEqual(third["service"], "worker")
        self.assertEqual(third["message"], "retry scheduled")

    def test_millisecond_timestamp_normalizes_to_seconds(self) -> None:
        parser = JSONLogParser()
        entry = parser.parse('{"timestamp":1790842531123,"message":"ms"}')
        self.assertEqual(entry["timestamp"], 1790842531)


class PlainTextFixtureTests(unittest.TestCase):
    def test_timestamp_level_service_and_raw_message(self) -> None:
        parser = TextLogParser()
        lines = fixture_lines("plain_text.log")
        entries = [parser.parse(line) for line in lines]

        self.assertTrue(all(entry is not None for entry in entries))
        first, second, third = entries

        self.assertEqual(first["timestamp"], 1790842680)
        self.assertEqual(first["level"], "info")
        self.assertEqual(first["service"], "gateway")
        self.assertEqual(first["fields"]["raw"], lines[0])

        self.assertEqual(second["timestamp"], 1790842741)
        self.assertEqual(second["level"], "warn")
        self.assertEqual(second["service"], "billing")

        self.assertEqual(third["level"], "debug")
        self.assertEqual(third["service"], "worker")


class NginxFixtureTests(unittest.TestCase):
    def test_combined_access_log_fields(self) -> None:
        parser = NginxLogParser()
        lines = fixture_lines("access.nginx.log")
        entries = [parser.parse(line) for line in lines]

        self.assertTrue(all(entry is not None for entry in entries))
        first, second, third = entries

        self.assertEqual(first["format"], "nginx")
        self.assertEqual(first["timestamp"], 1790842800)
        self.assertEqual(first["service"], "nginx")
        self.assertEqual(first["level"], "info")
        self.assertEqual(first["fields"]["remote_addr"], "203.0.113.10")
        self.assertEqual(first["fields"]["remote_user"], "alice")
        self.assertEqual(first["fields"]["request"], "GET /api/orders HTTP/1.1")
        self.assertEqual(first["fields"]["status"], 200)
        self.assertEqual(first["fields"]["body_bytes"], 512)

        self.assertEqual(second["level"], "error")
        self.assertEqual(second["fields"]["remote_user"], "-")
        self.assertEqual(second["fields"]["status"], 503)

        self.assertEqual(third["level"], "warn")
        self.assertEqual(third["fields"]["remote_user"], "bob")
        self.assertEqual(third["fields"]["status"], 404)


class AggregatorAndMalformedInputTests(unittest.TestCase):
    def test_aggregator_uses_nginx_parser_before_text_parser(self) -> None:
        aggregator = LogAggregator()
        line = fixture_lines("access.nginx.log")[0]

        self.assertTrue(aggregator._parse_line(line))
        self.assertEqual(len(aggregator.entries), 1)
        self.assertEqual(aggregator.entries[0]["format"], "nginx")
        self.assertEqual(aggregator.service_counts["nginx"], 1)

    def test_malformed_and_unsupported_lines_do_not_crash(self) -> None:
        aggregator = LogAggregator()
        for line in fixture_lines("malformed.log"):
            aggregator._parse_line(line)

        self.assertEqual(aggregator.get_summary()["total_entries"], len(aggregator.entries))

    def test_mixed_file_summary_and_json_export(self) -> None:
        lines: list[str] = []
        for filename in ("structured.jsonl", "plain_text.log", "access.nginx.log"):
            lines.extend(fixture_lines(filename))

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "mixed.log"
            output_path = Path(temp_dir) / "report.json"
            log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            aggregator = LogAggregator()
            self.assertEqual(aggregator.process_file(str(log_path)), len(lines))
            self.assertEqual(aggregator.get_summary()["total_entries"], len(lines))
            self.assertAlmostEqual(
                aggregator.get_summary()["time_range"]["duration_hours"],
                0.108333,
                places=5,
            )

            aggregator.export_json(str(output_path))
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["total_entries"], len(lines))
            self.assertEqual(len(report["entries"]), len(lines))


if __name__ == "__main__":
    unittest.main()
