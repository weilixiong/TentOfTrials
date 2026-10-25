#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Independent test fixtures and validation suite for LogParser implementations.
Addresses Issue #5: [Python] Add independent log parser fixtures

Covers:
- JSONLogParser
- TextLogParser
- NginxLogParser
- Boundary & malformed input handling
"""

import sys
import os
import unittest
from datetime import datetime

# 确保 tools 目录在 import 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser

# --- 独立构造的真实代表性测试固件 (Independent Hand-crafted Fixtures) ---

FIXTURES = {
    "json": [
        # 标准结构化日志
        '{"timestamp": "2026-03-15T08:30:00Z", "level": "INFO", "service": "auth-service", "message": "User logged in", "user_id": 1024}',
        '{"timestamp": "2026-03-15T08:31:12Z", "level": "ERROR", "service": "payment-api", "message": "Connection to payment gateway timed out", "code": 504}',
        '{"time": "2026-03-15 08:32:00", "severity": "WARN", "app": "inventory", "msg": "Low stock alert"}',
    ],
    "text": [
        # 标准纯文本日志
        "2026-03-15 10:15:30 [INFO] [order-service] Order #9876 created successfully",
        "2026-03-15 10:16:45 [WARN] [worker-pool] Task queue reached 80% capacity",
        "2026-03-15 10:17:10 [ERROR] [database] Deadlock detected during transaction execution",
    ],
    "nginx": [
        # Nginx 常用标准访问日志格式
        '192.168.1.100 - - [15/Mar/2026:12:00:00 +0000] "GET /api/v1/products HTTP/1.1" 200 4532 "-" "Mozilla/5.0"',
        '10.0.0.5 - admin [15/Mar/2026:12:01:23 +0000] "POST /api/v1/checkout HTTP/1.1" 500 128 "https://app.test/cart" "curl/8.1.0"',
    ],
    "malformed": [
        # 异常/畸形行，确保不抛出未捕获崩溃
        '{"incomplete_json": true, "broken_string": "unclosed',
        '',
        '   \n\t  ',
        'NOT_A_LOG_LINE_JUST_RANDOM_GARBAGE_WITHOUT_DELIMITERS_OR_TIMESTAMPS_9999999999',
        '{"timestamp": 123456789, "invalid": [null, {}]}',
    ]
}


class TestIndependentLogParserFixtures(unittest.TestCase):
    """验证各类解析器在独立固件下的鲁棒性与字段提取准确性"""

    def setUp(self):
        self.json_parser = JSONLogParser()
        self.text_parser = TextLogParser()
        self.nginx_parser = NginxLogParser()

    # --- JSON Parser Tests ---
    def test_json_parser_valid_fixtures(self):
        for line in FIXTURES["json"]:
            parsed = self.json_parser.parse(line)
            self.assertIsNotNone(parsed, f"JSON parser failed on valid line: {line}")
            self.assertIn("timestamp", parsed)
            self.assertIn("level", parsed)

        # 细粒度字段校验
        sample = self.json_parser.parse(FIXTURES["json"][0])
        self.assertEqual(sample.get("level"), "INFO")
        self.assertIn("auth-service", str(sample.get("service", "")))

    def test_json_parser_malformed_tolerance(self):
        for line in FIXTURES["malformed"]:
            try:
                parsed = self.json_parser.parse(line)
                # 即使无法解析，也应返回 None 或降级字典，严禁抛出未捕获异常崩溃
                self.assertTrue(parsed is None or isinstance(parsed, dict))
            except Exception as e:
                self.fail(f"JSONLogParser crashed on malformed line: {repr(line)}, error: {e}")

    # --- Text Parser Tests ---
    def test_text_parser_valid_fixtures(self):
        for line in FIXTURES["text"]:
            parsed = self.text_parser.parse(line)
            self.assertIsNotNone(parsed, f"Text parser failed on valid line: {line}")
            self.assertIn("timestamp", parsed)
            self.assertIn("level", parsed)

        sample = self.text_parser.parse(FIXTURES["text"][0])
        self.assertEqual(sample.get("level").upper(), "INFO")

    def test_text_parser_malformed_tolerance(self):
        for line in FIXTURES["malformed"]:
            try:
                parsed = self.text_parser.parse(line)
                self.assertTrue(parsed is None or isinstance(parsed, dict))
            except Exception as e:
                self.fail(f"TextLogParser crashed on malformed line: {repr(line)}, error: {e}")

    # --- Nginx Parser Tests ---
    def test_nginx_parser_valid_fixtures(self):
        for line in FIXTURES["nginx"]:
            parsed = self.nginx_parser.parse(line)
            self.assertIsNotNone(parsed, f"Nginx parser failed on valid line: {line}")

    def test_nginx_parser_malformed_tolerance(self):
        for line in FIXTURES["malformed"]:
            try:
                parsed = self.nginx_parser.parse(line)
                self.assertTrue(parsed is None or isinstance(parsed, dict))
            except Exception as e:
                self.fail(f"NginxLogParser crashed on malformed line: {repr(line)}, error: {e}")


def run_all_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestIndependentLogParserFixtures)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
