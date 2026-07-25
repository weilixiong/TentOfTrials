#!/usr/bin/env python3
"""Independent parser fixture tests for TentOfTrials log aggregator.

Hand-written representative log lines covering JSON, text, and nginx
formats. Validates parser output for timestamp, level, service, and
key fields. Includes malformed/unsupported line cases.
"""
import os
import sys
import unittest

# Add parent dir so we can import log_aggregator
TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS_DIR)
from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# ---------------------------------------------------------------------------
# JSON FIXTURES
# ---------------------------------------------------------------------------
JSON_FIXTURES = [
    {
        "line": '{"timestamp":"2024-03-15T10:30:00Z","level":"INFO","service":"payment-gateway","message":"Transaction processed successfully","amount":125.50}',
        "expect": {
            "format": "json",
            "level": "INFO",
            "service": "payment-gateway",
            "ts_present": True,
            "field_check": {"amount": 125.50},
        },
    },
    {
        "line": '{"time":"2024-03-15T10:30:01.123Z","level":"ERROR","service":"auth-service","msg":"Invalid token received","user_id":"usr-9876"}',
        "expect": {
            "format": "json",
            "level": "ERROR",
            "service": "auth-service",
            "ts_present": True,
            "field_check": {"user_id": "usr-9876"},
        },
    },
    {
        "line": '{"@timestamp":"2024-03-15T10:30:02.456+00:00","severity":"WARN","app":"inventory-manager","event":"Low stock alert","sku":"WIDGET-001"}',
        "expect": {
            "format": "json",
            "level": "WARN",
            "service": "inventory-manager",
            "ts_present": True,
            "field_check": {"sku": "WIDGET-001"},
        },
    },
    {
        "line": '{"timestamp":"2024-03-15T10:30:03Z","level":"DEBUG","logger":"data-pipeline","message":"Batch job started","batch_id":"batch-42"}',
        "expect": {
            "format": "json",
            "level": "DEBUG",
            "service": "data-pipeline",
            "ts_present": True,
            "field_check": {"batch_id": "batch-42"},
        },
    },
    {
        "line": '{"timestamp":"2024-03-15T10:30:04Z","level":"CRITICAL","service":"database-proxy","message":"Connection pool exhausted","active":50}',
        "expect": {
            "format": "json",
            "level": "CRITICAL",
            "service": "database-proxy",
            "ts_present": True,
            "field_check": {"active": 50},
        },
    },
    {
        "line": '{"timestamp":"2024-03-15T10:30:05Z","lvl":"info","service":"order-service","message":"Order confirmed","customer":"CUST-789"}',
        "expect": {
            "format": "json",
            "level": "info",
            "service": "order-service",
            "ts_present": True,
            "field_check": {"customer": "CUST-789"},
        },
    },
    {
        "line": '{"timestamp":"2024-03-15T10:30:06Z","level":"ERROR","service":"notification-hub","msg":"Email delivery failed","retry_count":3}',
        "expect": {
            "format": "json",
            "level": "ERROR",
            "service": "notification-hub",
            "ts_present": True,
            "field_check": {"retry_count": 3},
        },
    },
]

# ---------------------------------------------------------------------------
# TEXT FIXTURES
# ---------------------------------------------------------------------------
TEXT_FIXTURES = [
    {
        "line": "2024-03-15 10:30:00 INFO [auth-service] User login successful for user_id=usr-1234",
        "expect": {"format": "text", "level": "info", "service": "auth-service", "ts_present": True},
    },
    {
        "line": "2024-03-15 10:30:01 ERROR [database-proxy] Connection timeout after 30s",
        "expect": {"format": "text", "level": "error", "service": "database-proxy", "ts_present": True},
    },
    {
        "line": "2024-03-15 10:30:02 WARNING [payment-gateway] Rate limit approaching",
        "expect": {"format": "text", "level": "warn", "service": "payment-gateway", "ts_present": True},
    },
    {
        "line": "2024-03-15 10:30:03 DEBUG [data-pipeline] Processing batch batch-42",
        "expect": {"format": "text", "level": "debug", "service": "data-pipeline", "ts_present": True},
    },
    {
        "line": "2024-03-15 10:30:04 INFO [order-service] Order #ORD-9876 shipped",
        "expect": {"format": "text", "level": "info", "service": "order-service", "ts_present": True},
    },
    {
        "line": "2024-03-15T10:30:05 INFO [inventory-manager] Restocked SKU=WIDGET-001",
        "expect": {"format": "text", "level": "info", "service": "inventory-manager", "ts_present": True},
    },
    {
        "line": "Mar 15 10:30:06 web-server-01 CRITICAL [monitoring] Disk usage critical: 98%",
        "expect": {"format": "text", "level": "error", "service": "monitoring", "ts_present": True},
    },
    {
        "line": "2024-03-15 10:30:07 NOTICE [auth-service] Password reset request",
        "expect": {"format": "text", "level": "info", "service": "auth-service", "ts_present": True},
    },
    {
        "line": "2024-03-15 10:30:08 ERROR [notification-hub] SMS delivery failed",
        "expect": {"format": "text", "level": "error", "service": "notification-hub", "ts_present": True},
    },
    {
        "line": "2024-03-15 10:30:09 INFO PAYMENT-SERVICE: Transaction completed",
        "expect": {"format": "text", "level": "info", "service": "PAYMENT-SERVICE", "ts_present": True},
    },
]
