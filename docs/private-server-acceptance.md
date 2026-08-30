# Private-server acceptance test

The desktop app does not start or host an SCP:SL dedicated server. Start the
authorized server through its hosting panel or server-console workflow first.
This repository contains only the optional companion plugin source; it is not
a server runtime.

## Before testing

1. Start the private server and wait until its game port is listening.
2. Confirm the host and game port from the server panel. Do not use a public
   server entry as a substitute.
3. If using the optional companion, install the separately built plugin on the
   server and configure its owner-managed endpoint and token. The desktop app
   accepts loopback HTTP only for local testing; remote companion URLs must use
   HTTPS.
4. Start SCP:SL on the test PC and launch the auto-joiner.
5. Add or remember the private endpoint under **Servers**. Confirm its name and
   port before starting any join.

## Required runs

Run one test with an available slot and confirm `joined` plus the corresponding
log entry. Run a second test with the server full or rejecting connections and
confirm the retry delay, attempt counter, and eventual stop behavior. For Watch
Mode, verify that the app queries first and sends no game input until capacity
is detected.

Record the app version, SCP:SL version, Windows version, display resolution,
DPI scale, window mode, and the generated app report. Remove tokens and other
private data before sharing the report.

If the game port is not reachable, the acceptance test cannot begin; check the
hosting panel, firewall, port mapping, and server status rather than changing
the client retry logic.
