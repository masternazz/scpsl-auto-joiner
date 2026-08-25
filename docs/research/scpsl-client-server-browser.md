# How the SCP:SL client populates its server browser

Research date: 2026-08-24. Only first-party Northwood Studios materials, the installed SCP:SL 14.2.7 client, live Northwood responses, and Valve's official protocol documentation were used.

Labels used below:

- **Documented** — stated in official Northwood or Valve documentation.
- **Observed** — reproduced from the installed official client or a live Northwood/server response; this is implementation evidence, not a stable public API contract.
- **Inference** — the most likely explanation, but not explicitly confirmed by Northwood.

## Main finding

SCP:SL's initial Internet list is populated from Northwood's own central **LobbyList/Verified List**. The installed client selects a Northwood central server, downloads a signed LobbyList payload, validates its freshness/signature using a central public key, decodes each record, and applies local filters/sorting. The reviewed evidence does not show Steam's public master-server list as the source of those records.

The list already supplies the server's rich-text name, IP, port, `current/max` player count, version, friendly-fire/modded/whitelist flags, account/server IDs, Pastebin info ID, and official classification. A direct per-server query is therefore not required to initially render those fields.

## Lobby-list/master flow

### Documented

- Northwood defines its **Central Servers** as services that authenticate players and offer the **Verified List**. The Verified List is the public list available in-game and through Northwood's server-list site. [Northwood Community Server Guidelines, definitions D.1 and D.9](https://scpslgame.com/CSG.pdf)
- Northwood's browser guide says the Internet tab displays listed/verified servers, with filters for official, favourites, history, friends, empty, full, and whitelisted servers. It says ordering considers official class, geographic distance derived from server IP, account ID, and port. [Northwood Server List Sorting Guide](https://techwiki.scpslgame.com/books/server-guides/page/server-list-sorting-guide)
- Northwood calls the service the **LobbyList API**, but says third-party access is restricted and must be requested from its security team. [Northwood LobbyList API authentication](https://support.scpslgame.com/article/63)

### Observed in the official 14.2.7 client

- `Player.log` records a selected central server such as `SBG1 (https://SBG1.scpslgame.com/)`, public-key download/cache activity, and `Loading server list...`.
- The installed client's first-party IL2CPP metadata contains the relative request path:

  `lobbylist.php?format=json-signed-unix&version=2&minimal=1`

- A live request returned an outer JSON object with exactly `payload`, `timestamp`, and `signature`. `payload` is Base64-encoded JSON containing the server records. The successful request was `GET https://SBG1.scpslgame.com/lobbylist.php?format=json-signed-unix&version=2&minimal=1` with the single explicitly supplied header `User-Agent: UnityPlayer/6000.0.43f1 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)`. No `Authorization`, cookie, API key, or other secret was sent. It returned HTTP 200 and 1,125 records on the original 2026-08-24 test.
- **Reproduction note:** the superficially contradictory HTTP 403 came from requesting the same path with PowerShell's default User-Agent. At 2026-08-24 23:39:46 EDT, a four-case retest returned 403 from both `api.scpslgame.com` and `SBG1.scpslgame.com` with the default User-Agent, but HTTP 200 from both hosts with the Unity User-Agent above. Both successful responses had the signed wrapper and 1,128 records. The count is live and can change. This demonstrates User-Agent/edge filtering; it does not demonstrate a secret authentication credential.
- The client metadata includes `ServerListSigned` fields `payload`, `timestamp`, `signature`, `nonce`, and `error`, plus messages for an expired response, an invalid list signature, and refreshing/caching the central public key. This is strong implementation evidence that the client authenticates the list's origin/integrity and checks freshness before displaying it.

## Authentication and keys

Three unrelated credentials must not be conflated:

1. **LobbyList download/list-signing key.** **Observed:** the stock client downloads a central public key and validates the signed server-list response. A public key verifies data from Northwood; it is not a secret client credential. The observed LobbyList URL had no API key parameter. Reproduction required the Unity User-Agent above but no `Authorization`, cookie, account ID, server token, or other explicitly supplied credential. Future edge controls are still possible. Northwood states that third-party LobbyList API access is restricted, so successful retrieval should not be treated as permission or a stable public API. [LobbyList access policy](https://support.scpslgame.com/article/63)
2. **Player authentication token.** **Documented:** the online client authenticates through Central Servers; Northwood support refers separately to renewing the client's authentication token. This token is part of joining/authentication, not documented as the LobbyList credential. [Northwood client-authentication troubleshooting](https://techwiki.scpslgame.com/books/clients/page/im-getting-massive-walls-of-red-and-yellow-text-in-my-player-console-mentioning-a-task-was-cancelled)
3. **Server-owner keys.** **Documented:** `verkey.txt` binds a verified server to its IP (or to a provider's port arrangement), while the General API uses an Account ID plus a token generated by `!api reset`. Neither is the stock browser's list-signing public key. [Verification-key troubleshooting](https://techwiki.scpslgame.com/books/server-issues/page/im-getting-verification-passcode-is-not-correct-error-message) [General API authentication](https://support.scpslgame.com/article/61)

## Registration and verification

### Documented

- A server intended for the public Verified List must be externally reachable and configured with values including `server_name`, `server_ip`, `serverinfo_pastebin_id`, `max_players`, and contact information. Northwood explicitly describes `server_ip` as the address sent to the server list. [Gameplay Config Setup](https://techwiki.scpslgame.com/books/server-guides/page/2-gameplay-config-setup)
- Automatic verification is started with `!verify static` or `!verify dynamic`. Northwood's central service checks connectivity; the owner then accepts the Community Server Guidelines through a generated link. [Northwood verification guide](https://techwiki.scpslgame.com/books/server-guides/page/4-how-do-i-verify-my-server-a-step-by-step-guide)
- A bad/missing `verkey`, changed IP, extended downtime, or an unregistered port can prevent list updates or visibility. Verification is normally IP-bound and may be port-bound for hosting providers. [Verification-key troubleshooting](https://techwiki.scpslgame.com/books/server-issues/page/im-getting-verification-passcode-is-not-correct-error-message) [Port-not-registered troubleshooting](https://techwiki.scpslgame.com/books/server-issues/page/port-not-registered-error-in-scpsl-servers)

### Inference

The dedicated server periodically publishes its current record to Northwood's central service using its verification identity; Northwood validates/retains that record and includes eligible records in the signed LobbyList. The public sources document the endpoints of this process—server configuration/update errors and client list download—but not the complete registration request body or update cadence.

## Fields delivered to the client

The following schema was **observed** in the live Northwood minimal LobbyList payload:

| Field | Meaning/evidence |
|---|---|
| `serverId`, `accountId` | Northwood server and owner/account identifiers. Account ID and port are documented sorting keys. |
| `ip`, `port` | Connectable IPv4 endpoint. |
| `players` | A string such as `25/25`, containing current and maximum players. |
| `info` | Base64-encoded Unity Rich Text display name. Decoding observed records produced names such as `King's Playground Official Server - US East #1`. |
| `pastebin` | ID used for the server information/rules panel. |
| `version` | Server game version, e.g. `14.2.7`. |
| `friendlyFire`, `modded`, `whitelist` | Boolean browser indicators/filter data. These indicators are also described by Northwood's browser guide. |
| `legacy` | Boolean compatibility/status field present in the response. Its exact UI meaning is not publicly documented. |
| `official` | Textual official classification, e.g. `REGIONAL OFFICIAL`. |
| `officialCode` | Numeric official classification. Observed regional-official records carried `2`; the full numeric mapping is not published as a wire contract. |

The installed client's own `ServerListItem` type declares `accountId`, `serverId`, `ip`, `port`, `players`, `info`, `pastebin`, `version`, `friendlyFire`, `modded`, `whitelist`, `officialCode`, and a local `NameFilterPoints` member. The live response additionally included `legacy` and textual `official`; the deserializer can ignore fields it does not consume.

There is **no observed `verified` boolean**. **Inference:** inclusion in this Northwood-delivered list is itself the verified/listed state, while `official`/`officialCode` is a separate classification. This matches Northwood's distinction between the Verified List and official-server ordering, but Northwood does not publish the response schema as a supported contract.

## Direct per-server queries

- **Observed:** SCP:SL game servers can answer a Valve-style UDP `A2S_INFO` request. A direct test against `158.69.52.5:7778` returned `Northwood Official Server - Canada #2`. Valve documents that A2S_INFO can return a server name, map/game identity, current/max players, and related details. [Valve Server Queries: A2S_INFO](https://developer.valvesoftware.com/wiki/Server_queries#A2S_INFO)
- **Documented by Northwood:** server configuration exposes a query port shift and query-socket settings. [Gameplay Config Setup](https://techwiki.scpslgame.com/books/server-guides/page/2-gameplay-config-setup)
- **Not established:** no reviewed Northwood document or inspected first-party artifact proves that the stock browser sends A2S_INFO to every displayed server. Because the central LobbyList already supplies the rendered fields, the safest conclusion is that direct querying is an available per-server capability, not the source of the initial browser list.
- Valve also documents direct `PingServer`, `PlayerDetails`, and `ServerRules` calls in Steamworks, but their existence does not prove SCP:SL uses them. [Valve ISteamMatchmakingServers](https://partner.steamgames.com/doc/api/isteammatchmakingservers)

## Practical conclusion

For this auto-joiner, the cleanest source of server names would be Northwood's signed LobbyList because it already maps human names to IP/port and carries player/full-state data. However, Northwood explicitly restricts third-party LobbyList API access, so shipping an unofficial client against it without permission would be brittle and potentially contrary to its access policy. Direct A2S_INFO is a narrower fallback for resolving a known endpoint and does not require downloading the entire master list; OCR is unnecessary for either route.
