# Log Parser Fixtures & Validation

These are **independent** fixtures for `tools/log_aggregator.py`. Unlike the
legacy suite (which generated test data from the same parser logic and could
false-pass), every line here is **hand-written** from real-world log examples
and was never produced by the parser.

## Layout

```
tools/tests/fixtures/
  json_sample.log   3 structured JSON log lines (level/severity/lvl variants)
  text_sample.log   3 plain-text lines (ISO, standard, syslog timestamps)
  nginx_sample.log  2 nginx access-log lines (200 and 500 status)
  malformed.log     4 unsupported/partial lines that must NOT crash parsing
tools/tests/test_log_parser_fixtures.py   validation script
```

## What it checks

For each supported format the script asserts the extracted:

- **timestamp** — preserved (JSON) or parsed to a unix int (text/nginx)
- **level** — correct mapping (`error`/`warn`/`info`/`debug`)
- **service / format** — correct source field or `nginx`
- **key fields** — `message`, `request`, `status`, `remote_addr`, etc.

It also proves malformed lines (broken JSON, no-timestamp text, garbage) are
handled **without raising** — parsers return `None` or a best-effort result.

## Run it

```bash
python3 tools/tests/test_log_parser_fixtures.py
```

Exit `0` = all checks passed. This script is the required validation for the
log-parser fixtures bounty; it runs in isolation and has no other repo deps.
