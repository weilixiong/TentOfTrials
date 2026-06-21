import json
import re
import unittest

class LogParser:
    def parse_json(self, log_line):
        try:
            return json.loads(log_line)
        except json.JSONDecodeError:
            return None

    def parse_text(self, log_line):
        parts = log_line.split(' ')
        if len(parts) < 3:
            return None
        return {'timestamp': parts[0], 'level': parts[1], 'message': ' '.join(parts[2:])}

    def parse_nginx(self, log_line):
        regex = r'^(?P<ip>\d+\.\d+\.\d+\.\d+) - - \[(?P<time>[^]]+)\] "(?P<method>\w+) (?P<url>[^ ]+) HTTP/\d\.\d" (?P<status>\d+) (?P<size>\d+)$'
        match = re.match(regex, log_line)
        if match:
            return match.groupdict()
        return None

class TestLogParser(unittest.TestCase):
    def setUp(self):
        self.parser = LogParser()

    def test_parse_json(self):
        log_line = '{"key": "value"}'
        result = self.parser.parse_json(log_line)
        self.assertEqual(result, {'key': 'value'})

    def test_parse_text(self):
        log_line = '2023-10-01 INFO This is a log message'
        result = self.parser.parse_text(log_line)
        self.assertEqual(result, {'timestamp': '2023-10-01', 'level': 'INFO', 'message': 'This is a log message'})

    def test_parse_nginx(self):
        log_line = '127.0.0.1 - - [01/Oct/2023:10:00:00 +0000] "GET / HTTP/1.1" 200 1234'
        result = self.parser.parse_nginx(log_line)
        self.assertEqual(result, {'ip': '127.0.0.1', 'time': '01/Oct/2023:10:00:00 +0000', 'method': 'GET', 'url': '/', 'status': '200', 'size': '1234'})

    def test_parse_malformed(self):
        log_line = 'malformed log line'
        result = self.parser.parse_nginx(log_line)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()