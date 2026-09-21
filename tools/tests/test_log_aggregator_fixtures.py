import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "log_aggregator.py"
FIXTURES = Path(__file__).parent / "fixtures" / "log_parser"

SPEC = importlib.util.spec_from_file_location("log_aggregator", MODULE_PATH)
log_aggregator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = log_aggregator
SPEC.loader.exec_module(log_aggregator)

EXPECTED_TS = int(datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc).timestamp())


def fixture_line(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()[0]


class IndependentParserFixtureTests(unittest.TestCase):
    def test_json_fixture(self):
        entry = log_aggregator.JSONLogParser().parse(fixture_line("json.log"))
        self.assertIsNotNone(entry)
        self.assertEqual(entry["timestamp"], EXPECTED_TS)
        self.assertEqual(entry["level"], "ERROR")
        self.assertEqual(entry["service"], "billing-api")
        self.assertEqual(entry["format"], "json")
        self.assertEqual(entry["fields"]["request_id"], "req-fixture-1")

    def test_text_fixture(self):
        entry = log_aggregator.TextLogParser().parse(fixture_line("text.log"))
        self.assertIsNotNone(entry)
        self.assertEqual(entry["timestamp"], EXPECTED_TS)
        self.assertEqual(entry["level"], "warn")
        self.assertEqual(entry["service"], "worker")
        self.assertEqual(entry["format"], "text")
        self.assertIn("job-42", entry["fields"]["raw"])

    def test_nginx_fixture(self):
        entry = log_aggregator.NginxLogParser().parse(fixture_line("nginx.log"))
        self.assertIsNotNone(entry)
        self.assertEqual(entry["timestamp"], EXPECTED_TS)
        self.assertEqual(entry["level"], "error")
        self.assertEqual(entry["service"], "nginx")
        self.assertEqual(entry["format"], "nginx")
        self.assertEqual(entry["fields"]["remote_addr"], "203.0.113.7")
        self.assertEqual(entry["fields"]["remote_user"], "alice")
        self.assertEqual(entry["fields"]["status"], 503)
        self.assertEqual(entry["fields"]["request"], "GET /health?full=1 HTTP/1.1")

    def test_aggregator_detects_nginx_before_text_fallback(self):
        aggregator = log_aggregator.LogAggregator()
        parsed = aggregator._parse_line(fixture_line("nginx.log"))
        self.assertTrue(parsed)
        self.assertEqual(aggregator.entries[0]["format"], "nginx")

    def test_mixed_fixture_file_through_aggregator(self):
        lines = [
            fixture_line("json.log"),
            fixture_line("text.log"),
            fixture_line("nginx.log"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mixed.log"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            aggregator = log_aggregator.LogAggregator()
            self.assertEqual(aggregator.process_file(str(path)), 3)

        self.assertEqual([e["format"] for e in aggregator.entries], ["json", "text", "nginx"])
        self.assertEqual(aggregator.get_summary()["total_entries"], 3)
        self.assertEqual(aggregator.level_counts["error"], 2)
        self.assertEqual(aggregator.level_counts["warn"], 1)

    def test_json_epoch_and_iso_timestamps_are_supported(self):
        parser = log_aggregator.JSONLogParser()
        self.assertEqual(parser._coerce_timestamp(EXPECTED_TS), EXPECTED_TS)
        self.assertEqual(parser._coerce_timestamp(str(EXPECTED_TS)), EXPECTED_TS)
        self.assertEqual(parser._coerce_timestamp("2026-02-03T04:05:06Z"), EXPECTED_TS)
        self.assertIsNone(parser._coerce_timestamp("not-a-time"))

    def test_malformed_inputs_do_not_crash(self):
        malformed = (FIXTURES / "malformed.log").read_text(encoding="utf-8").splitlines()
        self.assertIsNone(log_aggregator.JSONLogParser().parse(malformed[0]))
        self.assertIsNone(log_aggregator.NginxLogParser().parse(malformed[1]))

        fallback = log_aggregator.TextLogParser().parse(malformed[1])
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback["format"], "text")
        self.assertEqual(fallback["level"], "unknown")


if __name__ == "__main__":
    unittest.main()
