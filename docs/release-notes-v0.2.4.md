## SCP:SL Auto-Joiner v0.2.4

### Retry reliability

- Keeps cold-start `-steam +connect` launch behavior.
- Uses the in-game background Direct Connect flow for warm retries.
- Treats a missed GUI connection start as transient and retries instead of stopping immediately with an unclear result.
- Adds clearer retry status text so the live feed explains what happened.

### Disclaimer

This is an early Windows build and has **not** been tested on every SCP:SL server, Windows configuration, monitor resolution, DPI setting, or game layout. Please expect bugs and [report them on GitHub](https://github.com/masternazz/scpsl-auto-joiner/issues) with your Windows version, display setup, reproduction steps, and app log.

The portable package must keep the `_internal` folder beside the EXE. The setup installer manages those files for you.
