# Private-server acceptance test

The desktop app does not start or host an SCP:SL dedicated server. Start the
authorized server through its hosting panel or server-console workflow first.
This repository contains only the optional companion plugin source; it is not
a server runtime.

## Before testing

1. Use the owner's private operations runbook to reach the authorized Pelican
   panel or management host. Start the SCP:SL test server and wait until the
   panel reports it running. Panel URLs, SSH aliases, server IDs, tokens, and
   private endpoints do not belong in this public repository.
2. Confirm from the Pelican console or authorized SSH session that startup has
   completed and the expected game/query ports are listening.
3. Confirm the host and game port from the server panel. Do not use a public
   server entry as a substitute.
4. If using the optional companion, install the separately built plugin on the
   server and configure its owner-managed endpoint and token. The desktop app
   accepts loopback HTTP only for local testing; remote companion URLs must use
   HTTPS.
5. Start SCP:SL on the test PC and launch the auto-joiner.
6. Add or remember the private endpoint under **Servers**. Confirm its name and
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
Pelican console, Wings status, firewall, port mapping, and server status rather
than changing the client retry logic.

## Candidate status recording

Record only non-sensitive outcomes in repository documentation. For the current
v0.3.35 candidate, the authorized server start and query-only A2S check have
completed successfully. Do not mark this acceptance test complete until all of
the required available-slot, controlled-full/retry, Watch Mode, and companion
deployment checks above have been run. Keep server identities, endpoints,
Steam IDs, tokens, panel details, and raw logs outside the repository.
