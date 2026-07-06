#!/usr/bin/env python3
"""Independent parser fixture tests for legacy log_aggregator parsers."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "log_parser"
LOG_AGGREGATOR_PATH = TOOLS_DIR / "log_aggregator.py"


def load_log_aggregator():
    spec = importlib.util.spec_from_file_location("log_aggregator", LOG_AGGREGATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["log_aggregator"] = module
    spec.loader.exec_module(module)
    return module


def read_fixture(name: str) -> list[str]:
    return [
        line
        for line in (FIXTURES_DIR / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class LogParserFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        mod = load_log_aggregator()
        cls.json_parser = mod.JSONLogParser()
        cls.text_parser = mod.TextLogParser()
        cls.nginx_parser = mod.NginxLogParser()
        cls.aggregator = mod.LogAggregator()

    def test_json_fixture_fields(self) -> None:
        lines = read_fixture("json_lines.txt")
        results = [self.json_parser.parse(line) for line in lines]
        self.assertTrue(all(entry is not None for entry in results))
        self.assertEqual(results[0]["level"], "INFO")
        self.assertEqual(results[0]["service"], "billing-api")
        self.assertEqual(results[0]["format"], "json")
        self.assertEqual(results[1]["level"], "ERROR")
        self.assertEqual(results[1]["service"], "auth-gateway")
        self.assertIn("Token validation failed", results[1]["message"])
        self.assertEqual(results[2]["level"], "debug")
        self.assertEqual(results[2]["service"], "worker")

    def test_text_fixture_fields(self) -> None:
        lines = read_fixture("text_lines.txt")
        results = [self.text_parser.parse(line) for line in lines]
        self.assertTrue(all(entry is not None for entry in results))
        self.assertEqual(results[0]["level"], "info")
        self.assertEqual(results[0]["service"], "billing")
        self.assertEqual(results[0]["format"], "text")
        self.assertIsNotNone(results[0]["timestamp"])
        self.assertEqual(results[1]["level"], "error")
        self.assertEqual(results[1]["service"], "auth")
        self.assertEqual(results[2]["level"], "warn")

    def test_nginx_fixture_fields(self) -> None:
        lines = read_fixture("nginx_lines.txt")
        results = [self.nginx_parser.parse(line) for line in lines]
        self.assertTrue(all(entry is not None for entry in results))
        self.assertEqual(results[0]["service"], "nginx")
        self.assertEqual(results[0]["fields"]["status"], 200)
        self.assertEqual(results[0]["level"], "info")
        self.assertEqual(results[1]["fields"]["status"], 401)
        self.assertEqual(results[1]["level"], "warn")
        self.assertEqual(results[2]["fields"]["status"], 503)
        self.assertEqual(results[2]["level"], "error")
        self.assertIsNotNone(results[2]["timestamp"])

    def test_malformed_lines_do_not_crash(self) -> None:
        lines = read_fixture("malformed_lines.txt")
        for line in lines:
            self.assertIsNone(self.json_parser.parse(line))
            self.assertIsNone(self.nginx_parser.parse(line))
            text_entry = self.text_parser.parse(line)
            self.assertIsNotNone(text_entry)
            self.assertEqual(text_entry["format"], "text")

        parsed = 0
        for line in lines:
            if self.aggregator._parse_line(line + "\n"):
                parsed += 1
        self.assertGreaterEqual(parsed, 1)
        self.assertLessEqual(parsed, len(lines))

    def test_aggregator_processes_fixture_mix(self) -> None:
        mixed = (
            read_fixture("json_lines.txt")
            + read_fixture("text_lines.txt")
            + read_fixture("nginx_lines.txt")
            + read_fixture("malformed_lines.txt")
        )
        count = sum(1 for line in mixed if self.aggregator._parse_line(line + "\n"))
        self.assertEqual(count, len(mixed))
        summary = self.aggregator.get_summary()
        self.assertEqual(summary["total_entries"], len(mixed))
        self.assertGreater(summary["total_entries"], 0)
        self.assertIn("billing-api", summary["by_service"])


if __name__ == "__main__":
    unittest.main()
# LEGACY: tools/tests/test_log_parser_fixtures.py
