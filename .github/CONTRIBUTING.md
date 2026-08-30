# Contributing

Read the relevant module and tests before changing code. Preserve compatibility
with saved servers, groups, settings, calibration profiles, themes, and
translation packs.

Live acceptance testing must use a server you own or are authorized to operate;
do not test against public SCP:SL servers. Never add game injection, memory
inspection, packet manipulation, anti-cheat bypasses, or credential handling.

Install dependencies and run the test suites in separate processes:

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 -m pytest tests --ignore=tests/test_gui_flow.py -q
py -3.13 -m pytest tests/test_gui_flow.py -q
```

Keep changes focused, add regression tests, preserve existing releases, and do
not commit build output, local AppData, credentials, temporary test folders,
or generated dependency directories.
