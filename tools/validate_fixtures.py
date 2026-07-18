#!/usr/bin/env python3
"""
Test fixture validator for log aggregator parsers.

This script validates that each parser correctly handles hand-written
fixture data without relying on parser-generated test samples.
"""

import json
import sys
from pathlib import Path

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser


def load_fixtures():
    """Load hand-written test fixtures from JSON file."""
    fixture_path = Path(__file__).parent / "test_fixtures.json"
    with open(fixture_path) as f:
        return json.load(f)


def validate_json_parser(parser: JSONLogParser, fixtures: list[dict]) -> tuple[int, int]:
    """Validate JSON parser against hand-written fixtures."""
    passed = 0
    failed = 0
    
    print("\n" + "=" * 60)
    print("JSON Log Parser Validation")
    print("=" * 60)
    
    for fixture in fixtures:
        raw = fixture["raw"]
        expected_level = fixture.get("expected_level", "").lower()
        expected_service = fixture.get("expected_service")
        
        result = parser.parse(raw)
        
        if result is None:
            print(f"  ❌ FAILED: Could not parse JSON log")
            print(f"     Input: {raw[:80]}...")
            failed += 1
            continue
        
        # Validate level
        actual_level = result.get("level", "").lower()
        if actual_level != expected_level:
            print(f"  ❌ FAILED: Level mismatch")
            print(f"     Expected: {expected_level}, Got: {actual_level}")
            print(f"     Input: {raw[:80]}...")
            failed += 1
            continue
        
        # Validate service
        actual_service = result.get("service")
        if actual_service != expected_service:
            print(f"  ❌ FAILED: Service mismatch")
            print(f"     Expected: {expected_service}, Got: {actual_service}")
            print(f"     Input: {raw[:80]}...")
            failed += 1
            continue
        
        # Validate timestamp is extracted (non-null)
        if result.get("timestamp") is None:
            print(f"  ❌ FAILED: Timestamp not extracted")
            print(f"     Input: {raw[:80]}...")
            failed += 1
            continue
        
        print(f"  ✅ PASSED: {expected_level.upper()} from {expected_service}")
        passed += 1
    
    return passed, failed


def validate_text_parser(parser: TextLogParser, fixtures: list[dict]) -> tuple[int, int]:
    """Validate text parser against hand-written fixtures."""
    passed = 0
    failed = 0
    
    print("\n" + "=" * 60)
    print("Text Log Parser Validation")
    print("=" * 60)
    
    for fixture in fixtures:
        raw = fixture["raw"]
        expected_level = fixture.get("expected_level", "").lower()
        expected_service = fixture.get("expected_service")
        
        result = parser.parse(raw)
        
        if result is None:
            print(f"  ❌ FAILED: Could not parse text log")
            print(f"     Input: {raw[:80]}...")
            failed += 1
            continue
        
        actual_level = result.get("level", "").lower()
        if actual_level != expected_level:
            print(f"  ❌ FAILED: Level mismatch")
            print(f"     Expected: {expected_level}, Got: {actual_level}")
            print(f"     Input: {raw[:80]}...")
            failed += 1
            continue
        
        actual_service = result.get("service")
        if actual_service != expected_service:
            print(f"  ❌ FAILED: Service mismatch")
            print(f"     Expected: {expected_service}, Got: {actual_service}")
            print(f"     Input: {raw[:80]}...")
            failed += 1
            continue
        
        print(f"  ✅ PASSED: {expected_level.upper()} from {expected_service}")
        passed += 1
    
    return passed, failed


def validate_nginx_parser(parser: NginxLogParser, fixtures: list[dict]) -> tuple[int, int]:
    """Validate nginx parser against hand-written fixtures."""
    passed = 0
    failed = 0
    
    print("\n" + "=" * 60)
    print("Nginx Log Parser Validation")
    print("=" * 60)
    
    for fixture in fixtures:
        raw = fixture["raw"]
        expected_level = fixture.get("expected_level", "").lower()
        expected_service = fixture.get("expected_service")
        
        result = parser.parse(raw)
        
        if result is None:
            print(f"  ❌ FAILED: Could not parse nginx log")
            print(f"     Input: {raw[:80]}...")
            failed += 1
            continue
        
        actual_level = result.get("level", "").lower()
        if actual_level != expected_level:
            print(f"  ❌ FAILED: Level mismatch")
            print(f"     Expected: {expected_level}, Got: {actual_level}")
            print(f"     Input: {raw[:80]}...")
            failed += 1
            continue
        
        actual_service = result.get("service")
        if actual_service != expected_service:
            print(f"  ❌ FAILED: Service mismatch")
            print(f"     Expected: {expected_service}, Got: {actual_service}")
            print(f"     Input: {raw[:80]}...")
            failed += 1
            continue
        
        # Validate required nginx fields are present
        fields = result.get("fields", {})
        required_fields = ["remote_addr", "status", "request"]
        for field in required_fields:
            if field not in fields:
                print(f"  ❌ FAILED: Missing field '{field}'")
                print(f"     Input: {raw[:80]}...")
                failed += 1
                continue
        
        print(f"  ✅ PASSED: {expected_level.upper()} from {expected_service}")
        passed += 1
    
    return passed, failed


def validate_malformed_logs(parser: JSONLogParser | TextLogParser | NginxLogParser, 
                           fixtures: list[dict]) -> tuple[int, int]:
    """Validate that malformed logs don't crash the parser."""
    passed = 0
    failed = 0
    
    print("\n" + "=" * 60)
    print("Malformed Log Handling Validation")
    print("=" * 60)
    
    for fixture in fixtures:
        raw = fixture.get("raw", "")
        should_parse = fixture.get("should_parse", True)
        
        if isinstance(parser, NginxLogParser) and not isinstance(raw, str):
            # Skip null checks for nginx parser (won't receive them anyway)
            continue
        
        try:
            result = parser.parse(raw)
            
            if should_parse:
                if result is None:
                    print(f"  ❌ FAILED: Expected parse to succeed but got None")
                    print(f"     Input: {str(raw)[:80]}...")
                    failed += 1
                else:
                    print(f"  ✅ PASSED: Handled gracefully")
                    passed += 1
            else:
                if result is not None:
                    print(f"  ❌ FAILED: Expected parse to fail but got result")
                    print(f"     Input: {str(raw)[:80]}...")
                    failed += 1
                else:
                    print(f"  ✅ PASSED: Correctly rejected malformed input")
                    passed += 1
                    
        except Exception as e:
            if should_parse:
                print(f"  ❌ FAILED: Parser crashed on valid log")
                print(f"     Error: {e}")
                print(f"     Input: {str(raw)[:80]}...")
                failed += 1
            else:
                print(f"  ✅ PASSED: Handled exception gracefully")
                passed += 1
    
    return passed, failed


def main():
    print("=" * 60)
    print("LOG PARSER FIXTURE VALIDATION")
    print("=" * 60)
    
    fixtures = load_fixtures()
    total_passed = 0
    total_failed = 0
    
    # Validate JSON parser
    json_parser = JSONLogParser()
    passed, failed = validate_json_parser(json_parser, fixtures["json_logs"])
    total_passed += passed
    total_failed += failed
    
    # Validate text parser
    text_parser = TextLogParser()
    passed, failed = validate_text_parser(text_parser, fixtures["text_logs"])
    total_passed += passed
    total_failed += failed
    
    # Validate nginx parser
    nginx_parser = NginxLogParser()
    passed, failed = validate_nginx_parser(nginx_parser, fixtures["nginx_logs"])
    total_passed += passed
    total_failed += failed
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total passed: {total_passed}")
    print(f"Total failed: {total_failed}")
    
    if total_failed > 0:
        print(f"\n❌ Validation FAILED ({total_failed} issues)")
        return 1
    else:
        print(f"\n✅ Validation PASSED (all fixtures valid)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
