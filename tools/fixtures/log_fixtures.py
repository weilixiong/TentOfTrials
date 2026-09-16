"""
Independent, representative log fixtures for Tent of Trials parser testing.
Hand-written fixtures representing authentic production logs across JSON,
plain text, and Nginx formats, including malformed and edge-case samples.
"""

JSON_FIXTURES = [
    {
        "raw": '{"timestamp": "2026-06-15T14:32:10Z", "level": "INFO", "service": "auth-service", "message": "User session created for user_98234", "user_id": "user_98234"}',
        "expected_format": "json",
        "expected_service": "auth-service",
        "expected_level": "INFO",
        "expected_message": "User session created for user_98234",
    },
    {
        "raw": '{"time": "2026-06-15T14:33:00Z", "severity": "ERROR", "logger": "orderbook", "msg": "Failed to settle order ORD-1029: insufficient balance"}',
        "expected_format": "json",
        "expected_service": "orderbook",
        "expected_level": "ERROR",
        "expected_message": "Failed to settle order ORD-1029: insufficient balance",
    },
    {
        "raw": '{"@timestamp": "2026-06-15T14:34:00Z", "lvl": "warn", "app": "gateway", "event": "Rate limit threshold reached for IP 192.168.1.50"}',
        "expected_format": "json",
        "expected_service": "gateway",
        "expected_level": "warn",
        "expected_message": "Rate limit threshold reached for IP 192.168.1.50",
    },
    {
        "raw": '{"timestamp": "2026-06-15T14:35:12Z", "level": "DEBUG", "service": "redis-cache", "message": "Cache hit for key session:f2633013"}',
        "expected_format": "json",
        "expected_service": "redis-cache",
        "expected_level": "DEBUG",
        "expected_message": "Cache hit for key session:f2633013",
    },
]

TEXT_FIXTURES = [
    {
        "raw": "2026-06-15 14:30:00 [backend] INFO Starting worker pool with 8 threads",
        "expected_format": "text",
        "expected_service": "backend",
        "expected_level": "info",
    },
    {
        "raw": "2026-06-15 14:31:22 [market] ERROR Database connection lost on pool-3",
        "expected_format": "text",
        "expected_service": "market",
        "expected_level": "error",
    },
    {
        "raw": "Jun 15 14:32:05 [frailbox] WARN High CPU usage detected in trial runner",
        "expected_format": "text",
        "expected_service": "frailbox",
        "expected_level": "warn",
    },
    {
        "raw": "2026-06-15 14:35:00 [engine] DEBUG Memory arena allocated 64MB",
        "expected_format": "text",
        "expected_service": "engine",
        "expected_level": "debug",
    },
]

NGINX_FIXTURES = [
    {
        "raw": '192.168.1.100 - user_admin [15/Jun/2026:14:30:00 +0000] "GET /api/v1/health HTTP/1.1" 200 128 "-" "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"',
        "expected_format": "nginx",
        "expected_service": "nginx",
        "expected_level": "info",
        "expected_status": 200,
        "expected_request": "GET /api/v1/health HTTP/1.1",
    },
    {
        "raw": '10.0.0.15 - - [15/Jun/2026:14:31:00 +0000] "POST /api/v1/orders HTTP/1.1" 400 64 "https://app.tent.io/" "TentClient/2.0"',
        "expected_format": "nginx",
        "expected_service": "nginx",
        "expected_level": "warn",
        "expected_status": 400,
        "expected_request": "POST /api/v1/orders HTTP/1.1",
    },
    {
        "raw": '10.0.0.22 - - [15/Jun/2026:14:32:00 +0000] "GET /api/v1/trades HTTP/1.1" 500 512 "-" "TentClient/2.0"',
        "expected_format": "nginx",
        "expected_service": "nginx",
        "expected_level": "error",
        "expected_status": 500,
        "expected_request": "GET /api/v1/trades HTTP/1.1",
    },
]

MALFORMED_FIXTURES = [
    '{"timestamp": "2026-06-15", "level": "INFO", corrupted_json',
    'plain string with invalid unparseable garbage !!!@#$%^&*()',
    '127.0.0.1 incomplete nginx line without proper fields',
    '',
    '   ',
    '{"not_a_dict_list": [1, 2, 3]}',
]
