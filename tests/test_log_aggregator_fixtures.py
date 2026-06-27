import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "log_aggregator"
sys.path.insert(0, str(ROOT / "tools"))

from log_aggregator import JSONLogParser, LogAggregator, NginxLogParser, TextLogParser


class IndependentLogParserFixtureTests(unittest.TestCase):
    def test_json_fixture_maps_structured_fields(self):
        line = (FIXTURES / "json_lines.log").read_text(encoding="utf-8").strip()
        expected_timestamp = int(
            datetime(2024, 1, 15, 12, 34, 56, tzinfo=timezone.utc).timestamp()
        )

        parsed = JSONLogParser().parse(line)

        self.assertEqual(parsed["timestamp"], expected_timestamp)
        self.assertEqual(parsed["level"], "ERROR")
        self.assertEqual(parsed["service"], "checkout")
        self.assertEqual(parsed["format"], "json")
        self.assertEqual(parsed["message"], "payment capture failed")
        self.assertEqual(parsed["fields"]["request_id"], "req_123")

    def test_plain_text_fixture_extracts_timestamp_level_and_service(self):
        line = (FIXTURES / "text_lines.log").read_text(encoding="utf-8").strip()
        expected_timestamp = int(
            datetime(2024, 1, 15, 12, 34, 56, tzinfo=timezone.utc).timestamp()
        )

        parsed = TextLogParser().parse(line)

        self.assertEqual(parsed["timestamp"], expected_timestamp)
        self.assertEqual(parsed["level"], "error")
        self.assertEqual(parsed["service"], "backend")
        self.assertEqual(parsed["format"], "text")
        self.assertIn("Failed to connect", parsed["message"])

    def test_nginx_fixture_extracts_access_log_fields(self):
        line = (FIXTURES / "nginx_access.log").read_text(encoding="utf-8").strip()
        expected_timestamp = int(
            datetime(2024, 1, 15, 12, 34, 56, tzinfo=timezone.utc).timestamp()
        )

        parsed = NginxLogParser().parse(line)

        self.assertEqual(parsed["timestamp"], expected_timestamp)
        self.assertEqual(parsed["level"], "error")
        self.assertEqual(parsed["service"], "nginx")
        self.assertEqual(parsed["format"], "nginx")
        self.assertEqual(parsed["fields"]["remote_addr"], "203.0.113.42")
        self.assertEqual(parsed["fields"]["status"], 500)
        self.assertEqual(parsed["fields"]["request"], "GET /api/orders HTTP/1.1")

    def test_malformed_fixture_does_not_crash_specific_parsers(self):
        lines = (FIXTURES / "malformed_lines.log").read_text(encoding="utf-8").splitlines()

        self.assertIsNone(JSONLogParser().parse(lines[0]))
        self.assertIsNone(JSONLogParser().parse(lines[1]))
        self.assertIsNone(NginxLogParser().parse(lines[0]))

    def test_cli_still_exports_summary_for_fixture_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "log_aggregator.py"),
                    "--input",
                    str(FIXTURES / "json_lines.log"),
                    "--output",
                    str(output),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["total_entries"], 1)
            self.assertEqual(report["entries"][0]["service"], "checkout")


if __name__ == "__main__":
    unittest.main()
