import pytest
from tools.log_aggregator import LogParser

@pytest.fixture
def json_log_line():
    return '''{"timestamp": "2023-10-01T12:34:56Z", "level": "ERROR", "service": "trial-service", "message": "Critical failure"}'''

@pytest.fixture
def text_log_line():
    return '''2023-10-01 12:34:56 [WARNING] payment-processor: Transaction timeout detected'''

@pytest.fixture
def nginx_log_line():
    return '''[01/Oct/2023:12:34:56 +0000] INFO 192.168.1.1 POST /api/trial - "Trial started"'''

@pytest.fixture
def malformed_log_line():
    return '''This is an invalid log entry with no structure'''

def test_json_parser(json_log_line):
    parser = LogParser()
    timestamp = parser.extract_timestamp(json_log_line)
    level = parser.extract_level(json_log_line)
    
    assert timestamp == 1696198496  # 2023-10-01T12:34:56Z in epoch
    assert level == 'error'

def test_text_parser(text_log_line):
    parser = LogParser()
    timestamp = parser.extract_timestamp(text_log_line)
    level = parser.extract_level(text_log_line)
    
    assert timestamp == 1696198496  # 2023-10-01 12:34:56 in epoch
    assert level == 'warn'

def test_nginx_parser(nginx_log_line):
    parser = LogParser()
    timestamp = parser.extract_timestamp(nginx_log_line)
    level = parser.extract_level(nginx_log_line)
    
    assert timestamp == 1696198496  # 01/Oct/2023:12:34:56 in epoch
    assert level == 'info'

def test_malformed_handling(malformed_log_line):
    parser = LogParser()
    timestamp = parser.extract_timestamp(malformed_log_line)
    level = parser.extract_level(malformed_log_line)
    
    assert timestamp is None
    assert level == ''  # extract_level returns empty string for unknown levels
