#!/usr/bin/env python3
"""
Validation tests for log parser fixtures

This script validates that the log parsers correctly handle independent
hand-written fixtures for JSON, plain text, and nginx log formats.
It also tests that malformed lines don't crash the parsers.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import log_aggregator
sys.path.insert(0, str(Path(__file__).parent.parent))

from log_aggregator import JSONLogParser, TextLogParser, NginxLogParser
from parser_fixtures import (
    JSON_FIXTURES,
    TEXT_FIXTURES,
    NGINX_FIXTURES,
    MALFORMED_FIXTURES
)


def validate_json_parser():
    """Validate JSON log parser against fixtures."""
    print("Testing JSON Log Parser...")
    parser = JSONLogParser()
    passed = 0
    failed = 0
    
    for fixture in JSON_FIXTURES:
        result = parser.parse(fixture["line"])
        expected = fixture["expected"]
        
        if result is None:
            print(f"  ✗ Failed to parse: {fixture['line'][:50]}...")
            failed += 1
            continue
        
        # Check key fields
        errors = []
        if result.get('format') != expected['format']:
            errors.append(f"format: expected {expected['format']}, got {result.get('format')}")
        if result.get('level') != expected['level']:
            errors.append(f"level: expected {expected['level']}, got {result.get('level')}")
        if result.get('service') != expected['service']:
            errors.append(f"service: expected {expected['service']}, got {result.get('service')}")
        if result.get('message') != expected['message']:
            errors.append(f"message: expected {expected['message']}, got {result.get('message')}")
        if result.get('timestamp') != expected['timestamp']:
            errors.append(f"timestamp: expected {expected['timestamp']}, got {result.get('timestamp')}")
        
        if errors:
            print(f"  ✗ Fixture failed: {fixture['line'][:50]}...")
            for error in errors:
                print(f"    - {error}")
            failed += 1
        else:
            print(f"  ✓ Validated: {fixture['line'][:50]}...")
            passed += 1
    
    print(f"JSON Parser: {passed} passed, {failed} failed")
    return failed == 0


def validate_text_parser():
    """Validate plain text log parser against fixtures."""
    print("\nTesting Text Log Parser...")
    parser = TextLogParser()
    passed = 0
    failed = 0
    
    for fixture in TEXT_FIXTURES:
        result = parser.parse(fixture["line"])
        expected = fixture["expected"]
        
        if result is None:
            print(f"  ✗ Failed to parse: {fixture['line'][:50]}...")
            failed += 1
            continue
        
        # Check key fields
        errors = []
        if result.get('format') != expected['format']:
            errors.append(f"format: expected {expected['format']}, got {result.get('format')}")
        if result.get('level') != expected['level']:
            errors.append(f"level: expected {expected['level']}, got {result.get('level')}")
        if result.get('service') != expected['service']:
            errors.append(f"service: expected {expected['service']}, got {result.get('service')}")
        # Message should contain the full line for text parser
        if result.get('message') != expected['message']:
            errors.append(f"message: expected {expected['message']}, got {result.get('message')}")
        
        if errors:
            print(f"  ✗ Fixture failed: {fixture['line'][:50]}...")
            for error in errors:
                print(f"    - {error}")
            failed += 1
        else:
            print(f"  ✓ Validated: {fixture['line'][:50]}...")
            passed += 1
    
    print(f"Text Parser: {passed} passed, {failed} failed")
    return failed == 0


def validate_nginx_parser():
    """Validate nginx log parser against fixtures."""
    print("\nTesting Nginx Log Parser...")
    parser = NginxLogParser()
    passed = 0
    failed = 0
    
    for fixture in NGINX_FIXTURES:
        result = parser.parse(fixture["line"])
        expected = fixture["expected"]
        
        if result is None:
            print(f"  ✗ Failed to parse: {fixture['line'][:50]}...")
            failed += 1
            continue
        
        # Check key fields
        errors = []
        if result.get('format') != expected['format']:
            errors.append(f"format: expected {expected['format']}, got {result.get('format')}")
        if result.get('level') != expected['level']:
            errors.append(f"level: expected {expected['level']}, got {result.get('level')}")
        if result.get('service') != expected['service']:
            errors.append(f"service: expected {expected['service']}, got {result.get('service')}")
        
        # Check nginx-specific fields
        for field, expected_value in expected['fields'].items():
            actual_value = result.get('fields', {}).get(field)
            if actual_value != expected_value:
                errors.append(f"fields.{field}: expected {expected_value}, got {actual_value}")
        
        if errors:
            print(f"  ✗ Fixture failed: {fixture['line'][:50]}...")
            for error in errors:
                print(f"    - {error}")
            failed += 1
        else:
            print(f"  ✓ Validated: {fixture['line'][:50]}...")
            passed += 1
    
    print(f"Nginx Parser: {passed} passed, {failed} failed")
    return failed == 0


def validate_malformed_lines():
    """Validate that malformed lines don't crash parsers."""
    print("\nTesting Malformed/Unsupported Lines...")
    parsers = {
        'JSON': JSONLogParser(),
        'Text': TextLogParser(),
        'Nginx': NginxLogParser()
    }
    
    all_passed = True
    
    for fixture in MALFORMED_FIXTURES:
        line = fixture["line"]
        should_parse = fixture["should_parse"]
        
        for parser_name, parser in parsers.items():
            try:
                result = parser.parse(line)
                
                if should_parse and result is None:
                    print(f"  ✗ {parser_name}: Expected to parse but failed: {repr(line[:30])}...")
                    all_passed = False
                elif not should_parse and result is not None:
                    print(f"  ⚠ {parser_name}: Unexpectedly parsed: {repr(line[:30])}...")
                    # This is not necessarily a failure - some parsers might handle it
                elif not should_parse and result is None:
                    print(f"  ✓ {parser_name}: Correctly rejected: {repr(line[:30])}...")
                
            except Exception as e:
                print(f"  ✗ {parser_name}: CRASHED on line: {repr(line[:30])}...")
                print(f"    Error: {e}")
                all_passed = False
    
    if all_passed:
        print("Malformed lines test: All parsers handled malformed lines gracefully")
    return all_passed


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Log Parser Fixture Validation")
    print("=" * 60)
    
    results = []
    results.append(("JSON Parser", validate_json_parser()))
    results.append(("Text Parser", validate_text_parser()))
    results.append(("Nginx Parser", validate_nginx_parser()))
    results.append(("Malformed Lines", validate_malformed_lines()))
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("All validation tests passed!")
        return 0
    else:
        print("Some validation tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())