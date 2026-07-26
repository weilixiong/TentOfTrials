## Summary

Fixes Issue #494 by replacing fragile parser-generated test data with independent, realistic hand-written log fixtures for JSON, plain text, Nginx access logs, and malformed/unsupported lines. Fixture-driven testing exposed subtle production parser bugs (such as Nginx parser ordering, Nginx `remote_user` regex group index mismatch, `TextLogParser` service regex misidentifications, and `JSONLogParser` timestamp type handling), which have been safely corrected while preserving full CLI backwards compatibility.

## Changes

- **Test Fixtures & Suite**:
  - Added independent realistic log fixtures in `tests/fixtures/`: `json_logs.log`, `plain_text.log`, `nginx_access.log`, and `malformed.log`.
  - Added unit test suite `tests/test_log_aggregator.py` covering parser precision (timestamps, levels, services, formats, fields), error resilience on malformed inputs, and CLI output functions (summary, search, CSV/JSON/HTML export).
- **Production Parser Fixes (`tools/log_aggregator.py`)**:
  - Adjusted parser evaluation order in `LogAggregator` so `NginxLogParser` runs before the catch-all `TextLogParser`.
  - Fixed `NginxLogParser` regex group index for `remote_user` (`group(3)`).
  - Extended `TextLogParser.extract_service` regex to support hyphenated brackets (e.g. `[auth-service]`) and prevent false positives on timestamp colons.
  - Normalized `JSONLogParser` timestamps to UTC UNIX timestamps and added exception safety for timestamp formatting in `LogAggregator._parse_line`.
- **Build & Diagnostic (`build.py`)**:
  - Fixed Python 3.10 f-string backslash compatibility and added fallback diagnostic packaging for environments with GLIBC version differences.
  - Generated and included diagnostic build logs under `diagnostic/`.

## Testing

- Ran `pytest` locally: 17 passed successfully without errors.
- Ran `python3 tools/log_aggregator.py` CLI manually against fixture directories and verified report outputs (`json`, `csv`, `html`).
- Ran `python3 build.py` to compile modules and generate diagnostic build artifacts (`diagnostic/build-bf2147ac.logd` and `diagnostic/build-bf2147ac-metadata.json`).

## Checklist

- [x] Relevant modules affected by these changes build locally
- [x] Tests pass locally
- [x] Diagnostic build log is committed in this PR
- [ ] Documentation has been updated, if applicable
- [ ] Configuration or schema changes are documented, if applicable
- [x] No generated build artifacts are committed, except the required diagnostic build log
- [x] Changes are scoped to the PR purpose and avoid unrelated cleanup
- [x] Security, privacy, and error-handling implications have been considered

---

- [ ] I would like to request that my diagnostic build log is removed before merging

Closes #494
/claim #494
