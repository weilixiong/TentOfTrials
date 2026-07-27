import json
import os
import pytest
from pathlib import Path
from tools.log_aggregator import LogAggregator

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def aggregator():
    return LogAggregator()

def test_json_log_fixture(aggregator):
    fixture_path = FIXTURES_DIR / "json_logs.log"
    assert fixture_path.exists(), "JSON log fixture file missing"
    count = aggregator.process_file(str(fixture_path))
    assert count > 0, "No entries parsed from JSON log fixture"
    summary = aggregator.get_summary()
    assert summary['total_entries'] == count
    assert 'json' in [e.get('format') for e in aggregator.entries]

def test_text_log_fixture(aggregator):
    fixture_path = FIXTURES_DIR / "text_logs.log"
    assert fixture_path.exists(), "Text log fixture file missing"
    count = aggregator.process_file(str(fixture_path))
    assert count > 0, "No entries parsed from text log fixture"
    summary = aggregator.get_summary()
    assert summary['total_entries'] == count
    assert 'text' in [e.get('format') for e in aggregator.entries]

def test_nginx_log_fixture(aggregator):
    fixture_path = FIXTURES_DIR / "nginx_logs.log"
    assert fixture_path.exists(), "Nginx log fixture file missing"
    count = aggregator.process_file(str(fixture_path))
    assert count > 0, "No entries parsed from nginx log fixture"
    summary = aggregator.get_summary()
    assert summary['total_entries'] == count
    assert 'nginx' in [e.get('format') for e in aggregator.entries]

def test_malformed_log_line(aggregator):
    # Malformed line should not crash parser
    malformed_line = "this is not a valid log line"
    result = aggregator._parse_line(malformed_line)
    assert result is False
    # Entries count should not increase
    initial_count = len(aggregator.entries)
    aggregator._parse_line(malformed_line)
    assert len(aggregator.entries) == initial_count

def test_mixed_log_file(aggregator):
    fixture_path = FIXTURES_DIR / "mixed_logs.log"
    assert fixture_path.exists(), "Mixed log fixture file missing"
    count = aggregator.process_file(str(fixture_path))
    assert count > 0, "No entries parsed from mixed log fixture"
    summary = aggregator.get_summary()
    assert summary['total_entries'] == count
    formats = set(e.get('format') for e in aggregator.entries)
    assert formats.intersection({'json', 'text', 'nginx'})
