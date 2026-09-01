# Product expansion guide

This guide covers the local-first features added after v0.3.34. Nothing here creates an account or uploads a server list, notes, history, calibration, or credentials.

## Explain and recover

Auto-Join shows **Why didn't it join?** after a Watch Mode or Immediate Auto-Join decision. Each entry names the evidence and a safe next action. Recovery never takes game input until you explicitly choose **Retry safely**. Use **Open Diagnostics** after a timeout, stale calibration, or UI recovery notice.

In Diagnostics, **Test my setup** checks the local game executable, `Player.log`, audio mute availability, calibration health, notifications, and optional Discord. Its A2S check is voluntary: select a saved server and press **Run checks again**. The target map displays saved controls relative to the game client; exact coordinates remain for technical support and bug reports.

**Create support bundle** writes a ZIP in AppData. It includes sanitized diagnostics, setup results, display metadata, decisions, and up to three redacted recent app logs. It excludes notes, history, raw endpoints, Discord state, tokens, and credentials.

## Organize and understand saved servers

Open **Servers → Organize** on a saved server to add local tags and notes. Search covers names, endpoints, tags, collections, and notes. Those fields stay on this PC and are never sent in a destination bundle, Discord presence, or support bundle.

Open **History** for local observations. The heatmap appears after at least eight samples and is labelled UTC. It describes your samples, not a prediction from a hosted service.

Settings includes compact cards, high contrast, and larger text. Motion still respects the operating system's reduced-motion setting.

## Alerts and safe backups

Slot alerts are off by default. When enabled, ordinary notifications announce a confirmed slot. Turn on **Actionable slot alerts** if you want Windows actions for **Join now**, **Keep watching**, and **Mute game and join**. With that option on, Watch Mode waits for your action rather than injecting game input automatically. If Windows cannot display toast actions, the app remains controllable from its window and tray.

**Create safe backup** exports a versioned ZIP containing saved servers, groups, profiles, settings, themes, local organization data, calibration profiles, text-pack metadata, and history summaries. It never exports Discord settings, companion tokens, credentials, or active audio state. Restore shows a preview, makes a safety backup, validates the archive, restores metadata, and rolls back in-memory data on a write failure. Translation-pack files are not copied from a backup archive; only their local metadata is restored.

Destination share links remain intentionally smaller: they contain only the server/group name, endpoints, and ordering. The import screen always previews them before saving or joining.

## Owned-server companion

`companion-plugin/` is an owner-installed LabAPI project, separate from the desktop installer and never loaded into the game client. Build it only with `LabAPI.dll` and `Assembly-CSharp.dll` from the exact target server release:

```powershell
$env:SL_REFERENCES = 'C:\path\to\SCPSL_Data\Managed'
dotnet build companion-plugin\AutoJoinerCompanion.csproj -c Release
```

Install the resulting DLL through the server owner's LabAPI plugin process. The plugin defaults to loopback HTTP. Remote use requires an owner-managed HTTPS reverse proxy. In Servers → Organize → Owned-server companion, enter the status URL and a token, then use **Test companion**. The token is protected locally with Windows DPAPI and excluded from exports.

The companion exposes only round phase, restart state, capacity, and a person's role/team if that Steam ID is explicitly allowlisted by the server owner. It does not provide Remote Admin controls, player lists, inventory, health, position, server credentials, or public-server role detection.
## Local organization

Use **Servers → Organize** to add tags, collections, and private notes to a
saved server. Collections can be created from the Servers page or typed while
organizing a server; assigning one keeps it available for later use. Search
matches names, endpoints, tags, collections, and notes. None of this private
organization data is included in a share link, Discord presence, or a support
bundle.

## Share-link actions

The setup installer registers `scpsl-autojoin://` links for the current Windows
user. Portable users can opt in from **Settings → Safe backup, alerts, and
accessibility → Register share-link actions**. This only registers the local
application as the link handler; it does not upload destinations or create an
account.

## Owned-server companion setup

The companion setup section in **Servers → Organize** is deliberately limited
to a server you own or administer. Install the separately built server DLL,
configure its server-console token, then paste the URL and token into the
desktop app. A remote URL must use HTTPS; loopback is allowed for local tests.
The test result shows health, round phase, capacity, source, and last update.
Personal role/team appears only when the server explicitly allowlists the
configured Steam ID.
