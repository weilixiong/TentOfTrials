import unittest
from pathlib import Path

from tools.log_aggregator import JSONLogParser, TextLogParser, NginxLogParser


class TestJSONLogParser(unittest.TestCase):
    def test_independent_json_fixture(self):
        fixture_path = Path(__file__).parent / "fixtures" / "json.log"

        line = fixture_path.read_text(encoding="utf-8").strip()
        result = JSONLogParser().parse(line)

        self.assertEqual(result["timestamp"], 1788863400)
        self.assertEqual(result["level"], "INFO")
        self.assertEqual(result["service"], "api")
        self.assertEqual(result["format"], "json")
        self.assertEqual(result["message"], "Request completed")
        self.assertEqual(result["fields"]["request_id"], "req-123")
        self.assertEqual(result["fields"]["status"], 200)


class TestTextLogParser(unittest.TestCase):
    def test_independent_text_fixture(self):
        fixture_path = Path(__file__).parent / "fixtures" / "text.log"

        line = fixture_path.read_text(encoding="utf-8").strip()
        result = TextLogParser().parse(line)

        self.assertEqual(result["timestamp"], 1788867930)
        self.assertEqual(result["level"], "info")
        self.assertEqual(result["service"], "api")
        self.assertEqual(result["format"], "text")
        self.assertEqual(result["message"], line)

class TestNginxLogParser(unittest.TestCase):
    def test_independent_nginx_fixture(self):
        fixture_path = Path(__file__).parent / "fixtures" / "nginx.log"

        line = fixture_path.read_text(encoding="utf-8").strip()
        result = NginxLogParser().parse(line)

        self.assertIsNotNone(result)
        self.assertEqual(result["level"], "info")
        self.assertEqual(result["service"], "nginx")
        self.assertEqual(result["format"], "nginx")
        self.assertEqual(result["message"], "GET /api/health HTTP/1.1")
        self.assertEqual(result["fields"]["remote_addr"], "192.168.1.10")
        self.assertEqual(result["fields"]["status"], 200)
        self.assertEqual(result["fields"]["body_bytes"], "123")

class TestMalformedLog(unittest.TestCase):
    def test_malformed_line_does_not_crash(self):
        malformed_line = "this is not a valid log line"

        json_result = JSONLogParser().parse(malformed_line)
        text_result = TextLogParser().parse(malformed_line)
        nginx_result = NginxLogParser().parse(malformed_line)

        self.assertIsNone(json_result)
        self.assertIsNotNone(text_result)
        self.assertIsNone(nginx_result)
if __name__ == "__main__":
    unittest.main()