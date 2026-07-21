import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "log_aggregator"
MODULE_PATH = TOOLS_DIR / "log_aggregator.py"

spec = importlib.util.spec_from_file_location("log_aggregator", MODULE_PATH)
log_aggregator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(log_aggregator)


def fixture_line(name: str, line_number: int = 0) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8").splitlines()[line_number]


class IndependentLogParserFixtureTests(unittest.TestCase):
    def test_json_fixture_preserves_key_structured_fields(self):
        parser = log_aggregator.JSONLogParser()

        first = parser.parse(fixture_line("json.log", 0))
        self.assertIsNotNone(first)
        self.assertEqual(first["format"], "json")
        self.assertEqual(first["timestamp"], "2026-07-20T18:42:11Z")
        self.assertEqual(first["level"], "ERROR")
        self.assertEqual(first["service"], "billing-api")
        self.assertEqual(first["message"], "payment capture failed")
        self.assertEqual(first["fields"]["request_id"], "req_42")

        second = parser.parse(fixture_line("json.log", 1))
        self.assertIsNotNone(second)
        self.assertEqual(second["timestamp"], "2026-07-20T18:43:01Z")
        self.assertEqual(second["level"], "INFO")
        self.assertEqual(second["service"], "worker")
        self.assertEqual(second["message"], "queue drained")

    def test_plain_text_fixture_extracts_timestamp_level_and_service(self):
        parser = log_aggregator.TextLogParser()

        entry = parser.parse(fixture_line("text.log", 0))
        self.assertIsNotNone(entry)
        self.assertEqual(entry["format"], "text")
        self.assertEqual(entry["timestamp"], int(datetime(2026, 7, 20, 18, 44, 22, tzinfo=timezone.utc).timestamp()))
        self.assertEqual(entry["level"], "warn")
        self.assertEqual(entry["service"], "inventory")
        self.assertIn("stock low", entry["message"])

        service_entry = parser.parse(fixture_line("text.log", 1))
        self.assertIsNotNone(service_entry)
        self.assertEqual(service_entry["level"], "error")
        self.assertEqual(service_entry["service"], "AUTH")

    def test_nginx_fixture_uses_nginx_parser_before_plain_text_fallback(self):
        aggregator = log_aggregator.LogAggregator()

        self.assertTrue(aggregator._parse_line(fixture_line("nginx.log", 0)))
        first = aggregator.entries[0]
        self.assertEqual(first["format"], "nginx")
        self.assertEqual(first["timestamp"], int(datetime(2026, 7, 20, 18, 45, 3, tzinfo=timezone.utc).timestamp()))
        self.assertEqual(first["level"], "warn")
        self.assertEqual(first["service"], "nginx")
        self.assertEqual(first["message"], "GET /api/lessons?q=dco HTTP/1.1")
        self.assertEqual(first["fields"]["remote_addr"], "203.0.113.10")
        self.assertEqual(first["fields"]["remote_user"], "alice")
        self.assertEqual(first["fields"]["status"], 404)
        self.assertEqual(first["fields"]["body_bytes"], "321")

        self.assertTrue(aggregator._parse_line(fixture_line("nginx.log", 1)))
        second = aggregator.entries[1]
        self.assertEqual(second["format"], "nginx")
        self.assertEqual(second["level"], "error")
        self.assertEqual(second["fields"]["status"], 502)

    def test_malformed_or_unsupported_lines_do_not_crash_parsers(self):
        self.assertIsNone(log_aggregator.JSONLogParser().parse(fixture_line("malformed.log", 0)))
        self.assertIsNone(log_aggregator.NginxLogParser().parse(fixture_line("malformed.log", 1)))

        aggregator = log_aggregator.LogAggregator()
        self.assertFalse(aggregator._parse_line(""))
        self.assertTrue(aggregator._parse_line(fixture_line("malformed.log", 1)))
        self.assertEqual(aggregator.entries[0]["format"], "text")
        self.assertEqual(aggregator.entries[0]["level"], "unknown")

    def test_cli_processes_independent_nginx_fixture_without_changing_output_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "--input",
                    str(FIXTURE_DIR / "nginx.log"),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["total_entries"], 2)
            self.assertEqual(report["summary"]["by_service"], {"nginx": 2})
            self.assertEqual(report["summary"]["by_level"], {"warn": 1, "error": 1})
            self.assertEqual(report["service_breakdown"]["nginx"]["total"], 2)
            self.assertEqual(report["service_breakdown"]["nginx"]["errors"], 1)
            self.assertEqual(report["service_breakdown"]["nginx"]["warns"], 1)


if __name__ == "__main__":
    unittest.main()
