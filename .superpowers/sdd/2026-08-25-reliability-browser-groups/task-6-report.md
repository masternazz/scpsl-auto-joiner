# Task 6 report - onboarding, diagnostics, settings, and docs

## Status

Completed.

## Commit

`4ff4900 feat: polish onboarding diagnostics and settings`

## Files

- `README.md`
- `config.py`
- `docs/server-groups.md`
- `gui.py`
- `installer.iss`
- `joiner.py`
- `notify.py`
- `resolver.py`
- `tests/test_config.py`
- `tests/test_gui_flow.py`
- `tests/test_joiner_flow.py`
- `tests/test_notify.py`

## Tests/output

- `python -m pytest tests/test_config.py tests/test_gui_flow.py -q`
  - `28 passed in 3.04s`
- `python -m pytest tests -q`
  - `109 passed in 10.52s`
- `python -m compileall -q gui.py config.py resolver.py joiner.py notify.py`
  - completed successfully
- `QT_SCALE_FACTOR=1` and `QT_SCALE_FACTOR=2` focused layout checks
  - `2 passed` at each scale

The added versioned-store regression test confirms the picker and group list
show display names rather than the storage keys `version`, `servers`, and
`groups`. The installer now keeps the visible branded name while using the
filesystem-safe `SCP-SL Auto-Joiner` name for shortcut and group paths.

## Concerns

The Inno Setup compiler (`ISCC`) is not installed on this machine, so the
installer change was source-reviewed but not compiled locally.
