# Resolving an SCP:SL server name from `IP:port`

Research date: 2026-08-24

## Conclusion

Use Steam `A2S_INFO` against the SCP:SL gameplay UDP endpoint. It can return the server's human-readable name directly and does not require a Northwood API key. `Player.log` is useful for discovering the endpoint and connection outcome, but it is not a reliable source of the server name. Northwood's LobbyList API is restricted, while its General API is primarily an owner-authenticated API for the caller's own servers.

## Findings

### `Player.log` does not reliably provide the server name

Northwood describes `Player.log` as a Unity-generated diagnostic log, not as a stable server-metadata interface ([Northwood Player.log guide](https://techwiki.scpslgame.com/books/common-debugging-steps/page/how-to-access-playerlog-report-files)). In the client log captured during this project's real join tests, SCP:SL emitted:

```text
Connecting to 158.69.52.5!
Connection IP set to 158.69.52.5, port: 7778
```

It did not emit the corresponding human-readable server name. Northwood does not publish a `Player.log` schema guaranteeing such a field. Therefore, the tool can safely use the log to learn `IP:port`, but should not depend on it to learn the name.

### Northwood API authentication

- **LobbyList API:** access is explicitly restricted to prevent abuse; Northwood instructs developers to contact its security team for access ([Northwood LobbyList authentication](https://support.scpslgame.com/article/63)). A normal client tool should assume it needs Northwood-granted credentials.
- **General API:** requests made from a different IP than the hosted server require the server account ID and an API key/token generated in that server's console. The ID/key may be omitted only when the request originates from the same IP that hosts the server ([Northwood General API authentication](https://support.scpslgame.com/article/61)). This is suitable for server owners querying their own servers, not for resolving arbitrary public endpoints.
- Northwood's in-game server browser does support searching listed servers by name and Direct Connect by IP, but that UI does not establish an unrestricted machine-readable API ([Northwood server-list guide](https://techwiki.scpslgame.com/books/server-guides/page/server-list-sorting-guide)).

### Steam `A2S_INFO` works directly with SCP:SL

Valve defines `A2S_INFO` as a UDP server-information request whose response includes the server name. Servers may first return `S2C_CHALLENGE` (`0x41`), after which the client must resend the request with the four-byte challenge ([Valve Server Queries: `A2S_INFO`](https://developer.valvesoftware.com/wiki/Server_queries#A2S_INFO)). Valve's Steamworks API likewise supports querying an individual game server directly by IP and port for updated details ([Valve `ISteamMatchmakingServers::PingServer`](https://partner.steamgames.com/doc/api/isteammatchmakingservers#PingServer)).

A live wire test against two current Northwood official SCP:SL endpoints confirmed the protocol:

1. Send `FF FF FF FF 54` followed by `Source Engine Query\0` to the gameplay **UDP** port.
2. SCP:SL replies `FF FF FF FF 41 <4-byte challenge>`.
3. Resend the same request with that challenge appended.
4. SCP:SL replies with the `0x49` A2S information response, including the null-terminated server name.

Observed results:

| Endpoint | Returned name |
|---|---|
| `158.69.52.5:7778` | `Northwood Official Server - Canada #2` |
| `158.69.52.5:7779` | `Northwood Official Server - Canada #3` |

This is separate from Northwood's optional `enable_query` feature, which its configuration guide describes as a **TCP** query protocol and disables by default ([Northwood gameplay configuration](https://techwiki.scpslgame.com/books/server-guides/page/2-gameplay-config-setup)). That TCP administration/query feature should not be confused with the UDP A2S response observed on the gameplay port.

## Recommended tool behavior

1. Read `IP:port` from `Player.log` after the user's connection attempt.
2. Resolve hostnames to an IP if necessary, then send `A2S_INFO` to that same UDP port.
3. Handle the `0x41` challenge response and parse the name from the subsequent `0x49` response.
4. Use a short timeout and a small retry count. If the endpoint is offline, firewalled, or behind a proxy that does not pass A2S packets, fall back to a naming prompt and cache the user's answer.
5. Normalize the returned display name before showing it. SCP:SL server names may contain Unity rich-text styling and dynamic name interpolation ([Northwood server-name guide](https://techwiki.scpslgame.com/books/server-guides/page/4-how-do-i-verify-my-server-a-step-by-step-guide), [Northwood command interpolation guide](https://techwiki.scpslgame.com/books/server-guides/page/command-interpolation)).

No OCR or Northwood API credential is needed for the normal `IP:port`-to-name path.
