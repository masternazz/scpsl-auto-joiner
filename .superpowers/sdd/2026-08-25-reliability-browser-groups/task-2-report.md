# Task 2 report

Status: complete

Commit: 32d24ba2d8c20a099c3038f229dd364b3fb7c0ee (`fix: harden log outcome tracking and rollover handling`)

Files:
- `logwatch.py`
- `tests/test_logwatch.py`

Tests/output:
- `python -m pytest tests/test_logwatch.py -q`: 24 passed
- `python -m pytest tests/test_logwatch.py tests/test_joiner_flow.py -q`: 33 passed
- `python -m pytest tests -q`: 80 passed
- `git diff --check`: passed

Concerns:
- Rejection is intentionally reported as `rejected_or_unknown`; later tasks must consume that explicit state.
- Rollover detection uses file identity and observed-size checks and intentionally skips the replacement file's existing prefix.

## Review fix

Status: complete

Commit: 2a5cc26c1ab1606d894cc1b4396be52cd69da367 (`fix: handle explicit log rejection outcomes in joiner`)

Files:
- `joiner.py`
- `tests/test_joiner_flow.py`

Tests/output:
- `python -m pytest tests/test_joiner_flow.py tests/test_logwatch.py -q`: 34 passed
- `python -m pytest tests -q`: 81 passed
- `git diff --check`: passed

Concerns:
- Legacy `rejected`/`cancelled` outcomes remain accepted for compatibility; new log outcomes `rejected_or_unknown` and `disconnected` now retry through the same path.
- Retry status deliberately says `rejected/full-or-unknown` and does not assert that a server is definitely full.
