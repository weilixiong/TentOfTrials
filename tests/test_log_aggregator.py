import sys
import unittest
from pathlib import Path

# Add tools directory to path to import log_aggregator
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "tools"))

from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser

class TestLogParsers(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = ROOT / "tests" / "fixtures"

    def test_json_parser(self):
        parser = JSONLogParser()
        lines = (self.fixtures_dir / "json.log").read_text().splitlines()
        
        # Line 1: Standard JSON
        res1 = parser.parse(lines[0])
        self.assertIsNotNone(res1)
        self.assertEqual(res1["timestamp"], "2026-07-13T01:00:00Z")
        self.assertEqual(res1["level"], "info")
        self.assertEqual(res1["service"], "auth")
        self.assertEqual(res1["message"], "User login successful")
        self.assertEqual(res1["format"], "json")

        # Line 2: Alternate key mappings (time, severity, logger, msg)
        res2 = parser.parse(lines[1])
        self.assertIsNotNone(res2)
        self.assertEqual(res2["timestamp"], "2026-07-13T01:05:00Z")
        self.assertEqual(res2["level"], "error")
        self.assertEqual(res2["service"], "db")
        self.assertEqual(res2["message"], "Connection timeout to postgres")

        # Line 3: Alternate key mappings (@timestamp, lvl, app, event)
        res3 = parser.parse(lines[2])
        self.assertIsNotNone(res3)
        self.assertEqual(res3["timestamp"], "2026-07-13T01:10:00Z")
        self.assertEqual(res3["level"], "warn")
        self.assertEqual(res3["service"], "payment")
        self.assertEqual(res3["message"], "Stripe API response delayed")

        # Line 4: Malformed JSON (should return None, not crash)
        res4 = parser.parse(lines[3])
        self.assertNullOrNone(res4)

    def test_text_parser(self):
        parser = TextLogParser()
        lines = (self.fixtures_dir / "text.log").read_text().splitlines()

        # Line 1: standard timestamp, level, service
        res1 = parser.parse(lines[0])
        self.assertIsNotNone(res1)
        self.assertEqual(res1["level"], "info")
        self.assertEqual(res1["service"], "auth")
        self.assertEqual(res1["format"], "text")

        # Line 2: ISO8601 timestamp and error level
        res2 = parser.parse(lines[1])
        self.assertIsNotNone(res2)
        self.assertEqual(res2["level"], "error")
        self.assertIsNone(res2["service"])

        # Line 3: No timestamp, bracketed service, level
        res3 = parser.parse(lines[2])
        self.assertIsNotNone(res3)
        self.assertEqual(res3["level"], "warn")
        self.assertEqual(res3["service"], "db")

        # Line 4: Completely unsupported plain text line (should parse message but no tags)
        res4 = parser.parse(lines[3])
        self.assertIsNotNone(res4)
        self.assertEqual(res4["level"], "unknown")
        self.assertIsNone(res4["service"])
        self.assertEqual(res4["message"], "not a log line at all")

    def test_nginx_parser(self):
        parser = NginxLogParser()
        lines = (self.fixtures_dir / "nginx.log").read_text().splitlines()

        # Line 1: Status 200 -> level info
        res1 = parser.parse(lines[0])
        self.assertIsNotNone(res1)
        self.assertEqual(res1["level"], "info")
        self.assertEqual(res1["service"], "nginx")
        self.assertEqual(res1["format"], "nginx")
        self.assertEqual(res1["fields"]["remote_addr"], "127.0.0.1")
        self.assertEqual(res1["fields"]["status"], 200)

        # Line 2: Status 401 -> level warn
        res2 = parser.parse(lines[1])
        self.assertIsNotNone(res2)
        self.assertEqual(res2["level"], "warn")
        self.assertEqual(res2["fields"]["status"], 401)

        # Line 3: Status 500 -> level error
        res3 = parser.parse(lines[2])
        self.assertIsNotNone(res3)
        self.assertEqual(res3["level"], "error")
        self.assertEqual(res3["fields"]["status"], 500)

        # Line 4: Malformed nginx (should return None, not crash)
        res4 = parser.parse(lines[3])
        self.assertNullOrNone(res4)

    def assertNullOrNone(self, val):
        self.assertTrue(val is None)

if __name__ == "__main__":
    unittest.main()
