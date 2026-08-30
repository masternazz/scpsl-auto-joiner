# Next feature opportunities for SCP:SL Auto-Joiner

Research date: 2026-08-30

## Scope

This report compares the application's current feature set with capabilities exposed by SCP: Secret Laboratory, Valve server queries, Discord, and Windows. It ranks additions by user value, technical feasibility, and risk. Community reports are included only as evidence of user pain; technical claims use first-party documentation or existing repository research.

## Existing baseline

The application already provides saved servers, ordered retry groups, A2S_INFO status and name queries, connection-result detection from `Player.log`, GUI retry automation, calibration, Windows notifications, game-audio muting, translation-pack management, themes, diagnostics, updates, and local import/export.

New work should deepen the waiting-and-joining workflow rather than create unrelated tools.

## Ranked opportunities

### 1. Query-first Watch Mode

Add a low-interruption mode that monitors a saved server through A2S_INFO and performs GUI joining only when the server reports an open slot. Require two consistent samples or a short debounce before acting, because server counts can be stale and a reported slot does not reserve capacity.

This directly addresses the repeated community complaint that full servers lack a queue and require constant manual refreshing. It also reduces how often the app must foreground SCP:SL and interact with its Unity UI.

The application already parses server name, current players, maximum players, password state, and latency from A2S_INFO, so this is an extension of an existing capability rather than a new protocol.

Sources:

- [Valve Steam server queries](https://developer.valvesoftware.com/wiki/Server_queries#A2S_INFO)
- [Valve ISteamMatchmakingServers](https://partner.steamgames.com/doc/api/isteammatchmakingservers)
- [Community request for a queue](https://www.reddit.com/r/SCPSecretLab/comments/1l7jgkl/)
- [Community report about stale/full counts](https://www.reddit.com/r/SCPSecretLab/comments/zbt2xm/)

### 2. Local server history and smart recommendations

Record timestamped local samples for saved servers: online state, player count, capacity, and latency. Use them to show:

- busiest and quietest hours;
- typical latency and availability;
- recent uptime;
- estimated likelihood of a slot opening;
- a recommendation among the user's saved servers or within a retry group.

All data can remain local. This does not require Northwood LobbyList access, accounts, telemetry, or player identities. Sampling must be rate-limited and performed only for saved servers.

Valve documents that individual server queries expose live server details. Steam also models local favorites and history, confirming that favorites/history are normal server-browser concepts, although a third-party application should maintain its own store rather than assume it may initialize SCP:SL's Steamworks context.

Sources:

- [Valve ISteamMatchmaking](https://partner.steamgames.com/doc/api/isteammatchmaking)
- [Valve game-server browser overview](https://partner.steamgames.com/doc/features/multiplayer/game_servers)

### 3. Notification-area companion mode

Allow the app to continue Watch Mode or Auto-Join while its main window is hidden. The notification-area menu should expose only high-value actions: show status, open the app, pause/stop, mute/unmute SCP:SL, and quit. Notifications should be optional and limited to slot detected, joined, stopped, or failed.

This matches the application's long-running background task. Windows guidance treats the notification area as an appropriate place for background-task status and controls, provided the user can disable it and quit the process.

Sources:

- [Microsoft notification-area guidance](https://learn.microsoft.com/en-us/windows/win32/uxguide/winenv-notification)
- [Microsoft app-notification overview](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/)

### 4. Per-server profiles and smarter group policy

Store behavior with each saved server instead of applying one global configuration to everything. Useful profile fields are retry delay, query interval, attempt timeout, preferred input/navigation mode, mute-while-waiting, and notification preference.

Groups can then support explicit policies:

- first available server;
- lowest latency among servers with a slot;
- preferred order with fallback;
- minimum/maximum population;
- stop after one pass or loop.

This uses only existing local data and A2S_INFO results. It makes groups substantially more useful without requiring a global browser.

### 5. Optional Discord Rich Presence

Offer an opt-in presence that can display states such as `Watching Canada #3`, `Waiting for a slot`, or `Joined — 24/25`, with an elapsed timer. Never publish a private server name or endpoint unless the user explicitly enables sharing for that server.

Discord officially supports details, state, elapsed timestamps, party size, buttons, and direct desktop Rich Presence without user authentication when the Discord desktop client is running.

A join button is technically possible through a join secret, but it should launch this utility through a registered protocol and ask the recipient to confirm the destination. It must not expose raw private endpoints in public presence data. Full friend/lobby features would add OAuth and a larger social subsystem and should not be the first version.

Sources:

- [Discord Rich Presence](https://docs.discord.com/developers/platform/rich-presence)
- [Discord direct Rich Presence and presence fields](https://docs.discord.com/developers/discord-social-sdk/development-guides/setting-rich-presence)
- [Discord game invites](https://docs.discord.com/developers/discord-social-sdk/development-guides/managing-game-invites)

### 6. Shareable destination bundles

Export one server or ordered group as a small JSON file or custom application link. Import should show a confirmation screen with server names and endpoints before saving anything. Files and links must never carry executable settings, theme CSS, passwords, or calibration coordinates.

This provides most of the useful social-joining experience without accounts or a hosted backend. It can later become the payload behind a Discord join action.

### 7. Game-version-aware calibration health

Associate calibration with the detected game version, client rectangle, monitor, DPI, and window mode. Warn when those conditions differ, preserve the old profile, and offer a target-preview diagnostic before joining. Keep automatic client-relative coordinates as the default.

This does not eliminate Unity UI variation, but it turns silent misclicks into a clear compatibility state and reduces unnecessary recalibration.

### 8. Translation-pack update checking

For packs installed from a GitHub repository or release, compare the stored source revision with the latest release or commit only when the user requests a check. Show changed metadata and require confirmation before replacing a pack; preserve the existing backup-and-restore behavior.

This is useful but secondary to the core joining workflow.

### 9. Optional owned-server companion

For servers controlled by the user, an optional LabAPI plugin could publish authenticated round state, the user's role, restart state, and accurate joinability to the desktop app. LabAPI is Northwood's official server-side framework and exposes server/player events.

This must remain separate and optional. A client-only application cannot reliably infer roles on arbitrary public servers, and server administration features require authorization.

Sources:

- [Northwood LabAPI](https://github.com/northwood-studios/LabAPI)
- [Northwood Remote Admin authorization](https://techwiki.scpslgame.com/books/server-guides/page/remote-admin-panel)

## Features not recommended without external approval or a larger product change

### Unrestricted global SCP:SL browser

Northwood states that LobbyList API access is restricted and must be requested. The app should not ship against an observed internal endpoint or imitate the Unity client's User-Agent. Continue querying known, user-saved endpoints unless Northwood grants access.

Source: [Northwood LobbyList API access](https://support.scpslgame.com/article/63)

### Steam-native notifications or matchmaking ownership

Steam game notifications require a publisher key and a hosted server, and that key must not ship in a client. The utility does not own SCP:SL's Steam App ID or publisher integration. Windows notifications and Discord presence are appropriate alternatives.

Source: [Steam game notifications](https://partner.steamgames.com/doc/features/game_notifications)

### Public-server role detection

`Player.log` is a diagnostic log without a published schema that guarantees the player's current role. Reliable role events belong in an authorized server-side companion. Do not add memory inspection, injection, packet manipulation, or anti-cheat-adjacent behavior.

Source: [Northwood anti-cheat policy](https://scpslgame.com/Ban_Policy.pdf)

### Automatic password or credential sharing

Do not store or distribute private-server passwords, Remote Admin credentials, authentication tokens, or Northwood API keys through destination bundles or Discord presence.

## Recommended roadmap

1. Query-first Watch Mode and notification-area controls.
2. Local server history, availability estimates, and per-server profiles.
3. Smarter group policies using current player count and latency.
4. Shareable destination bundles.
5. Optional privacy-controlled Discord Rich Presence.
6. Calibration health and translation-pack update checking.
7. Optional LabAPI companion only if owned-server integration becomes a real user need.

The first three items reinforce the application's central promise: let the user choose where they want to play, then wait with minimal interruption until the app can get them in.
