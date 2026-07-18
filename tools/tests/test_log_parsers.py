import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestJSONLogParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = JSONLogParser()

    def _load_fixture(self, name):
        path = os.path.join(FIXTURES_DIR, name)
        with open(path) as f:
            return [line.strip() for line in f if line.strip()]

    def test_parses_valid_json_logs(self):
        lines = self._load_fixture("json_logs.log")
        parsed = [self.parser.parse(l) for l in lines]
        self.assertEqual(len(parsed), 15)
        self.assertTrue(all(e is not None for e in parsed))

    def test_extracts_timestamp(self):
        lines = self._load_fixture("json_logs.log")
        entry = self.parser.parse(lines[0])
        self.assertEqual(entry["timestamp"], "2024-03-15T08:12:33")

    def test_extracts_level(self):
        lines = self._load_fixture("json_logs.log")
        levels = [
            "info", "info", "error", "warn", "debug",
            "error", "info", "critical", "info", "warn",
            "error", "info", "fatal", "info", "trace",
        ]
        for line, expected in zip(lines, levels):
            entry = self.parser.parse(line)
            self.assertEqual(entry["level"], expected, f"Expected {expected}, got {entry['level']} for {line[:60]}")

    def test_extracts_service(self):
        lines = self._load_fixture("json_logs.log")
        entry = self.parser.parse(lines[0])
        self.assertEqual(entry["service"], "api_gateway")

    def test_level_mappings_json(self):
        line = '{"timestamp": "2024-03-15T08:12:33", "level": "FATAL", "service": "test", "message": "test"}'
        entry = self.parser.parse(line)
        self.assertEqual(entry["level"], "FATAL")

    def test_different_json_keys(self):
        line = '{"time": "2024-03-15T12:00:00", "severity": "WARN", "logger": "myapp", "msg": "test message"}'
        entry = self.parser.parse(line)
        self.assertEqual(entry["timestamp"], "2024-03-15T12:00:00")
        self.assertEqual(entry["level"], "WARN")
        self.assertEqual(entry["service"], "myapp")
        self.assertEqual(entry["message"], "test message")

    def test_rejects_invalid_json(self):
        line = "not valid json at all {{{"
        self.assertIsNone(self.parser.parse(line))

    def test_rejects_non_dict_json(self):
        line = json.dumps([1, 2, 3])
        self.assertIsNone(self.parser.parse(line))


class TestNginxLogParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = NginxLogParser()

    def _load_fixture(self, name):
        path = os.path.join(FIXTURES_DIR, name)
        with open(path) as f:
            return [line.strip() for line in f if line.strip()]

    def test_parses_nginx_logs(self):
        lines = self._load_fixture("nginx_access.log")
        parsed = [self.parser.parse(l) for l in lines]
        self.assertEqual(len(parsed), 15)
        self.assertTrue(all(e is not None for e in parsed))

    def test_extracts_service(self):
        lines = self._load_fixture("nginx_access.log")
        entry = self.parser.parse(lines[0])
        self.assertEqual(entry["service"], "nginx")

    def test_extracts_status_code(self):
        lines = self._load_fixture("nginx_access.log")
        entry = self.parser.parse(lines[0])
        self.assertEqual(entry["fields"]["status"], 200)

    def test_level_from_status_2xx(self):
        lines = self._load_fixture("nginx_access.log")
        entry = self.parser.parse(lines[0])
        self.assertEqual(entry["level"], "info")

    def test_level_from_status_4xx(self):
        lines = self._load_fixture("nginx_access.log")
        entry = self.parser.parse(lines[4])
        self.assertEqual(entry["fields"]["status"], 401)
        self.assertEqual(entry["level"], "warn")

    def test_level_from_status_5xx(self):
        lines = self._load_fixture("nginx_access.log")
        entry = self.parser.parse(lines[5])
        self.assertEqual(entry["fields"]["status"], 500)
        self.assertEqual(entry["level"], "error")

    def test_extracts_request_line(self):
        lines = self._load_fixture("nginx_access.log")
        entry = self.parser.parse(lines[0])
        self.assertEqual(entry["message"], "GET /api/v1/users HTTP/1.1")

    def test_extracts_remote_addr(self):
        lines = self._load_fixture("nginx_access.log")
        entry = self.parser.parse(lines[0])
        self.assertEqual(entry["fields"]["remote_addr"], "192.168.1.10")

    def test_extracts_referer(self):
        lines = self._load_fixture("nginx_access.log")
        entry = self.parser.parse(lines[0])
        self.assertEqual(entry["fields"]["referer"], "https://app.example.com/dashboard")

    def test_handles_304_status(self):
        line = '192.168.1.1 - - [15/Mar/2024:10:00:00 +0000] "GET /static/file.js HTTP/1.1" 304 0 "-" "curl/7.88.1"'
        entry = self.parser.parse(line)
        self.assertEqual(entry["fields"]["status"], 304)
        self.assertEqual(entry["level"], "info")

    def test_rejects_malformed_nginx_line(self):
        self.assertIsNone(self.parser.parse("not an nginx log line"))
        self.assertIsNone(self.parser.parse(""))


class TestTextLogParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = TextLogParser()

    def _load_fixture(self, name):
        path = os.path.join(FIXTURES_DIR, name)
        with open(path) as f:
            return [line.strip() for line in f if line.strip()]

    def test_parses_plain_text_logs(self):
        lines = self._load_fixture("plain_text.log")
        parsed = [self.parser.parse(l) for l in lines]
        self.assertEqual(len(parsed), 15)
        self.assertTrue(all(e is not None for e in parsed))

    def test_extracts_timestamp(self):
        lines = self._load_fixture("plain_text.log")
        entry = self.parser.parse(lines[0])
        self.assertIsNotNone(entry["timestamp"])
        self.assertIsInstance(entry["timestamp"], int)

    def test_extracts_level(self):
        lines = self._load_fixture("plain_text.log")
        levels = [
            "info", "info", "error", "warn", "info",
            "error", "info", "info", "warn", "error",
            "info", "error", "info", "warn", "error",
        ]
        for line, expected in zip(lines, levels):
            entry = self.parser.parse(line)
            self.assertEqual(
                entry["level"], expected,
                f"Expected {expected}, got {entry['level']} for: {line[:80]}"
            )

    def test_extracts_service_from_brackets(self):
        lines = self._load_fixture("plain_text.log")
        services = [
            "gateway", "gateway", "payment", "payment",
            "pipeline", "pipeline", "scheduler", "scheduler",
            "balancer", "balancer", "cdn_purge", "cdn_purge",
            "backup", "backup", "backup",
        ]
        for line, expected in zip(lines, services):
            entry = self.parser.parse(line)
            self.assertEqual(
                entry["service"], expected,
                f"Expected {expected}, got {entry['service']} for: {line[:80]}"
            )

    def test_level_from_keyword(self):
        entry = self.parser.parse("2024-03-15 12:00:00 [test] CRITICAL: disk failure")
        self.assertEqual(entry["level"], "error")
        entry = self.parser.parse("2024-03-15 12:00:00 [test] FATAL: something terrible")
        self.assertEqual(entry["level"], "error")
        entry = self.parser.parse("2024-03-15 12:00:00 [test] TRACE: entry point")
        self.assertEqual(entry["level"], "debug")

    def test_rejects_empty_line(self):
        self.assertIsNone(self.parser.parse(""))
        self.assertIsNone(self.parser.parse("   "))

    def test_fallback_format_field(self):
        entry = self.parser.parse("2024-03-15 12:00:00 [test] INFO: some message")
        self.assertEqual(entry["format"], "text")


class TestSyslogParsingWithTextParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = TextLogParser()

    def _load_fixture(self, name):
        path = os.path.join(FIXTURES_DIR, name)
        with open(path) as f:
            return [line.strip() for line in f if line.strip()]

    def test_parses_syslog_messages(self):
        lines = self._load_fixture("syslog_messages.log")
        parsed = [self.parser.parse(l) for l in lines]
        self.assertEqual(len(parsed), 15)
        self.assertTrue(all(e is not None for e in parsed))

    def test_syslog_extracts_level(self):
        lines = self._load_fixture("syslog_messages.log")
        expected_levels = [
            "unknown", "unknown", "error", "unknown", "unknown",
            "error", "error", "error", "unknown", "unknown",
            "unknown", "unknown", "unknown", "unknown", "unknown",
        ]
        for line, expected in zip(lines, expected_levels):
            entry = self.parser.parse(line)
            self.assertEqual(
                entry["level"], expected,
                f"Expected {expected}, got {entry['level']} for: {line[:80]}"
            )


if __name__ == "__main__":
    unittest.main()
