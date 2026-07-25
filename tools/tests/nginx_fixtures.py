# Nginx log fixtures - hand-written representative lines.

NGINX_FIXTURES = [
    {
        "line": '192.168.1.10 - - [15/Mar/2024:10:30:00 +0000] "GET /api/v1/orders HTTP/1.1" 200 1234 "https://app.example.com" "Mozilla/5.0"',
        "expect": {
            "format": "nginx",
            "level": "info",
            "service": "nginx",
            "ts_present": True,
            "field_check": {"status": 200, "remote_addr": "192.168.1.10"},
        },
    },
    {
        "line": '10.0.0.5 - admin [15/Mar/2024:10:30:01 +0000] "POST /api/v1/auth/login HTTP/1.1" 200 512 "https://app.example.com/login" "Mozilla/5.0"',
        "expect": {
            "format": "nginx",
            "level": "info",
            "service": "nginx",
            "ts_present": True,
            "field_check": {"status": 200, "remote_user": "admin"},
        },
    },
    {
        "line": '172.16.0.1 - - [15/Mar/2024:10:30:02 +0000] "GET /api/v1/products/9999 HTTP/1.1" 404 89 "https://app.example.com" "curl/7.68.0"',
        "expect": {
            "format": "nginx",
            "level": "warn",
            "service": "nginx",
            "ts_present": True,
            "field_check": {"status": 404},
        },
    },
    {
        "line": '192.168.2.20 - - [15/Mar/2024:10:30:03 +0000] "DELETE /api/v1/cache/invalidate HTTP/1.1" 500 234 "https://admin.example.com" "Mozilla/5.0"',
        "expect": {
            "format": "nginx",
            "level": "error",
            "service": "nginx",
            "ts_present": True,
            "field_check": {"status": 500},
        },
    },
    {
        "line": '10.0.0.5 - admin [15/Mar/2024:10:30:04 +0000] "PUT /api/v1/users/settings HTTP/1.1" 200 1024 "https://app.example.com/settings" "Mozilla/5.0"',
        "expect": {
            "format": "nginx",
            "level": "info",
            "service": "nginx",
            "ts_present": True,
            "field_check": {"status": 200},
        },
    },
    {
        "line": '192.168.3.30 - - [15/Mar/2024:10:30:05 +0000] "GET /health HTTP/1.1" 200 2 "http://localhost:8080" "kube-probe/1.28"',
        "expect": {
            "format": "nginx",
            "level": "info",
            "service": "nginx",
            "ts_present": True,
            "field_check": {"status": 200},
        },
    },
    {
        "line": '10.0.0.5 - - [15/Mar/2024:10:30:06 +0000] "GET /static/bundle.js HTTP/1.1" 304 0 "https://app.example.com" "Mozilla/5.0"',
        "expect": {
            "format": "nginx",
            "level": "info",
            "service": "nginx",
            "ts_present": True,
            "field_check": {"status": 304},
        },
    },
    {
        "line": '172.16.0.100 - - [15/Mar/2024:10:30:07 +0000] "POST /api/v1/upload HTTP/1.1" 413 156 "https://app.example.com" "Mozilla/5.0"',
        "expect": {
            "format": "nginx",
            "level": "warn",
            "service": "nginx",
            "ts_present": True,
            "field_check": {"status": 413},
        },
    },
    {
        "line": '192.168.4.40 - - [15/Mar/2024:10:30:08 +0000] "CONNECT api.stripe.com:443 HTTP/1.1" 200 0 "-" "Mozilla/5.0"',
        "expect": {
            "format": "nginx",
            "level": "info",
            "service": "nginx",
            "ts_present": True,
            "field_check": {"status": 200},
        },
    },
    {
        "line": '10.0.0.5 - admin [15/Mar/2024:10:30:09 +0000] "GET /api/v1/admin/dashboard HTTP/1.1" 403 67 "https://admin.example.com" "Mozilla/5.0"',
        "expect": {
            "format": "nginx",
            "level": "warn",
            "service": "nginx",
            "ts_present": True,
            "field_check": {"status": 403},
        },
    },
]

# Malformed / unsupported lines - should not crash parsing
MALFORMED_FIXTURES = [
    "this is just a random string with no log structure at all",
    "{bad json: no closing brace",
    "---SYSTEM BOOT--- kernel loaded ok",
    "[2024/03/15 10:30:00] [info] [module] message with mixed brackets",
    "",
]
