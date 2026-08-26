# Saved servers and groups

The app stores saved server display names, endpoints, and ordered groups only in its local AppData folder. It does not read restricted SCP:SL browser services or claim server roles.

Use the **Servers** page to search saved entries, refresh an entry through its public A2S_INFO response, edit its display name or endpoint, and create an ordered group. Starting a group tries its members in the saved order after a rejection or timeout. Enable group looping to restart from the first server after the final member; otherwise, one rejected pass ends the group run. Global retry and runtime limits still apply.

The picker accepts both older flat server files and the current versioned local store. Storage metadata such as `version`, `servers`, and `groups` is never shown as a server choice.

The primary path uses the supported direct-connect launch and targeted background input. If a Unity build ignores that path, the foreground compatibility mode restores the previous foreground window and cursor position. Calibration is optional and records local control positions; it does not require clicking the game.
