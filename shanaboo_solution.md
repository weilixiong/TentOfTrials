 ```diff
--- a/tools/log_aggregator.py
+++ b/tools/log_aggregator.py
@@ -1,4 +1,4 @@
-#!/usr/bin/env python3
+#!/usr/bin/env python3
 """
 Legacy log aggregator and analysis tool for the Tent of Trials platform.
 
@@ -23,6 +23,7 @@
 import csv
 import gzip
 import io
+import unittest
 import json
 import logging
 import os
@@ -32,7 +33,7 @@
 from concurrent.futures import ThreadPoolExecutor
 from datetime import datetime, timedelta, timezone
 from pathlib import Path
-from typing import Any, Counter, Dict, List, Optional, Tuple
+from typing import Any, Dict, List, Optional, Tuple
 from collections import defaultdict, Counter
 
 logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
@@ -97,7 +98,7 @@ def extract_level(self, line: str) -> str:
         for pattern, level in self.LEVEL_PATTERNS:
             if re.search(pattern, line, re.IGNORECASE):
                 return leve
-                return level
+        return level
         return 'unknown'
 
 
@@ -105,7 +106,7 @@ class JSONLogParser(LogParser):
     """Parser for JSON-formatted log lines."""
 
     def parse(self, line: str) -> Optional[Dict[str, Any]]:
-        try:
+        try:
             data = json.loads(line)
             if not isinstance(data, dict):
                 return None
@@ -123,7 +124,7 @@ def parse(self, line: str) -> Optional[Dict[str, Any]]:
                 'timestamp": timestamp,
                 "level": level,
                 "service": service,
-                "message": message,
+                "message": message,
                 "raw": line,
             }
         except (json.JSONDecodeError, ValueError):
@@ -134,7 +135,7 @@ class TextLogParser(LogParser):
     """Parser for plain text log lines."""
 
     TIMESTAMP_RE = re.compile(
-        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'
+        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'
     )
 
     def parse(self, line: str) -> Optional[Dict[str, Any]]:
@@ -142,7 +143,7 @@ def parse(self, line: str) -> Optional[Dict[str, Any]]:
         if not timestamp:
             return None
 
-        level = self.extract_level(line)
+        level = self.extract_level(line)
 
         service = 'unknown'
         service_match = re.search(r'\[([^\]]+)\]', line)
@@ -153,7 +154,7 @@ def parse(self, line: str) -> Optional[Dict[str, Any]]:
             "timestamp": timestamp,
             "level": level,
             "service": service,
-            "message": line.strip(),
+            "message": line.strip(),
             "raw": line,
         }
 
@@ -162,7 +163,7 @@ class NginxLogParser(LogParser):
     """Parser for nginx access logs."""
 
     NGINX_PATTERN = re.compile(
-        r'(\d+\.\d+\.\d+\.\d+)\s+-\s+-\s+\[([^\]]+)\]\s+"(\w+)\s+([^\s]+)\s+HTTP/[\d\.]+"\s+(\d+)\s+(\d+)'
+        r'(\d+\.\d+\.\d+\.\d+)\s+-\s+-\s+\[([^\]]+)\]\s+"(\w+)\s+([^\s]+)\s+HTTP/[\d\.]+"\s+(\d+)\s+(\d+)'
     )
 
     def parse(self, line: str) -> Optional[Dict[str, Any]]:
@@ -172,7 +173,7 @@ def parse(self, line: str) -> Optional[Dict[str, Any]]:
 
         ip, timestamp_str, method, path, status, size = match.groups()
 
-        timestamp = None
+        timestamp = None
         for fmt in ['%d/%b/%Y:%H:%M:%S %z', '%d/%b/%Y:%H:%M:%S']:
             try:
                 dt = datetime.strptime(timestamp_str, fmt)
@@ -186,7 +187,7 @@ def parse(self, line: str) -> Optional[Dict[str, Any]]:
             "timestamp": timestamp,
             "level": "info",
             "service": "nginx",
-            "message": f"{method} {path} {status}",
+            "message": f"{method} {path} {status}",
             "raw": line,
             "ip": ip,
             "method": method,
@@ -194,7 +195,7 @@ def parse(self, line: str) -> Optional[Dict[str, Any]]:
             "status": int(status),
             "size": int(size),
         }
-        return result
+        return result
 
 
 class SyslogParser(LogParser):
@@ -202,7 +203,7 @@ class SyslogParser(LogParser):
 
     SYSLOG_PATTERN = re.compile(
         r'<\d+>\d+\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+\+\d{2}:\d{2})\s+(\S+)\s+(\S+)\s+-\s+(.*)'
-    )
+    )
 
     def parse(self, line: str) -> Optional[Dict[str, Any]]:
         match = self.SYSLOG_PATTERN.match(line)
@@ -218,7 +219,7 @@ def parse(self, line: str) -> Optional[Dict[str, Any]]:
             "timestamp": timestamp,
             "level": self.extract_level(line),
             "service": service,
-            "message": message,
+            "message": message,
             "raw": line,
         }
 
@@ -227,7 +228,7 @@ class LogAggregator:
     """Aggregates logs from multiple sources and formats."""
 
     PARSERS = {
-        'json': JSONLogParser(),
+        'json': JSONLogParser(),
         'text': TextLogParser(),
         'nginx': NginxLogParser(),
         'syslog': SyslogParser(),
@@ -236,7 +237,7 @@ class LogAggregator:
     def __init__(self):
         self.entries: List[Dict[str, Any]] = []
 
-    def detect_format(self, line: str) -> str:
+    def detect_format(self, line: str) -> str:
         """Detect the log format of a line."""
         if line.startswith('{'):
             return 'json'
@@ -248,7 +249,7 @@ def detect_format(self, line: str) -> str:
             return 'text'
 
     def parse_line(self