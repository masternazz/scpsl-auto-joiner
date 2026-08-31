# Discord Rich Presence

Discord Rich Presence is optional, local, and disabled by default. The app
continues to start, watch servers, and join normally when Discord is closed,
not installed, or unavailable.

## Setup

1. Create an application in the Discord Developer Portal.
2. Copy its public **Application ID** into Settings → Discord application.
3. In the application's Rich Presence assets, upload the purple S mark using
   the asset key `scpsl-autojoin-s`.
4. Enable Discord Rich Presence in the app.

Only the public Application ID belongs in the desktop app. Never paste a client
secret, bot token, or OAuth credential.

## What friends can see

By default, Discord shows only a general Auto-Joiner state such as “Watching
for a slot.” It does not show a server name, player count, endpoint, password,
or private local data.

To share a particular saved destination, open its server profile and enable
**Share this destination on Discord**. That allows the destination name and a
Discord Join request for that one saved server. To show a player count too,
also enable the global **Share player counts** setting.

The app never displays raw server endpoints in Rich Presence text.

## Join behavior

Discord's Join action carries a compact, versioned destination bundle through
the local Discord IPC connection. When a recipient has Auto-Joiner installed,
the app opens the normal destination-import preview. The recipient must review
and explicitly import it; the app never saves or joins a server automatically.

Destination bundles are limited to server name, host, and port. They exclude
passwords, tokens, AppData, settings, calibration, history, themes, and other
private data.

## Troubleshooting

- **“Discord is unavailable”** — Start the Discord desktop client. This state
  is harmless and is retried lazily on the next presence update.
- **No icon** — Verify the Rich Presence asset key is exactly
  `scpsl-autojoin-s`; Discord may cache assets briefly.
- **No server detail or Join action** — Enable sharing for that specific saved
  server in its profile. Player count additionally needs the global setting.
- **Friend cannot join** — They need a current Auto-Joiner install. The import
  preview is intentional; it protects against unwanted joins.

Discord's Rich Presence and Join capability are documented by Discord in its
[Rich Presence guide](https://docs.discord.com/developers/platform/rich-presence)
and [game-invites guide](https://docs.discord.com/developers/discord-social-sdk/development-guides/managing-game-invites).
