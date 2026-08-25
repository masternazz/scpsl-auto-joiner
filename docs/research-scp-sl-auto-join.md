# Research: SCP:SL auto-join tools and native capabilities

Research date: 2026-08-25

## Bottom line

SCP: Secret Laboratory already provides the server browser, server display names, player counts, filters, server information, Re-join, and Direct Connect. Steam supplies the game-launch/authentication layer; it does not appear to provide an SCP:SL-specific “keep retrying until a slot opens” feature.

Our app is therefore a client-side convenience layer around existing game behavior. Its custom work is saving friendly server names, launching SCP:SL, retrying rejected/full connections, reading the game log for connection state, and presenting that process in a separate UI.

## What SCP:SL provides

- The official SCP:SL support/wiki material describes a Server Browser with Internet, Favourites, Official, History, and Friends views, plus Search, Re-join, Direct Connect, and Refresh actions. It also describes player counts, server names, filters, and server information. [Official server-list sorting guide](https://techwiki.scpslgame.com/books/server-guides/page/server-list-sorting-guide)
- Northwood’s own 10.0 update notes describe the revamped browser, Favorites, Rejoin, server information, and connection-progress presentation. [Northwood 10.0 update notes](https://en.scpslgame.com/index.php?title=Updates/10.0.0)
- Northwood exposes a central lobby-list endpoint. A Northwood developer explained that `https://api.scpslgame.com/lobbylist.php?format=json` returns the server list and that it is refreshed about every 30 seconds. [Northwood developer answer](https://steamcommunity.com/app/700330/discussions/1/1752399065077956568/)
- SCP:SL also has server-info/API endpoints for server owners, including player counts for servers they control. [Official SCP:SL API support article](https://support.scpslgame.com/article/61)
- Direct Connect is an in-game SCP:SL action that accepts an IP/hostname, so the game—not Steam—is the component that understands the server endpoint and performs the SCP:SL connection. [Official server-list guide](https://techwiki.scpslgame.com/books/server-guides/page/server-list-sorting-guide)

## What Steam provides

- Steam can launch a game and pass launch parameters. Steamworks documents launch query parameters and game-launch URL handling, but these are general platform mechanisms rather than an SCP:SL queue/retry feature. [Steamworks ISteamApps documentation](https://partner.steamgames.com/doc/api/isteamapps)
- Steam’s overlay can expose a game-server change request when a user chooses to join a friend’s game. That is a separate social/overlay flow and is not the same as polling a full SCP:SL server and retrying Direct Connect. [Steamworks overlay documentation](https://partner.steamgames.com/doc/features/overlay)
- I found no official Steam documentation describing an automatic retry-until-slot-opens feature for SCP:SL.

## Did other people build something similar?

I searched public GitHub results and SCP:SL community/official sources for SCP:SL auto-join, full-server retry, and server-browser automation. I did not find an obvious public clone that combines the exact features of this project: a Windows GUI, saved friendly names, automatic launch, full/rejected retry, log-based state detection, background input, and packaged updates.

There are adjacent tools:

- Public SCP:SL server-browser websites display names, addresses, versions, and player counts, such as [Kigen’s browser](https://kigen.co/scpsl/browser.php?table=y). These are browsers/list views, not desktop auto-join retry clients.
- Server-side plugins and frameworks such as [EXILED](https://github.com/ExMod-Team/EXILED) and [MultiAdmin](https://github.com/ServerMod/MultiAdmin) manage or extend dedicated servers. MultiAdmin includes starting another configured server when one is full, which is a server-hosting workflow—not a player-side client that waits to join one server. [MultiAdmin](https://github.com/ServerMod/MultiAdmin)
- Plugins such as [DynamicServerNames](https://github.com/furyashnyy/DynamicServerNames) alter the name shown in the browser. They confirm that the browser name is server-provided, but they do not implement client auto-join.

This is not proof that no private or unindexed tool exists; it means no clear public equivalent appeared in the sources searched.

## Implications for our design

1. We should continue treating SCP:SL’s own list/name/player data and `Player.log` as the authoritative game-side signals.
2. We should not claim the app adds a new Steam or SCP:SL feature. It automates an existing Direct Connect workflow.
3. A future “browse all servers inside our app” feature could use the official lobby-list endpoint, but it would need rate limiting, handling of central-server availability, and careful review of Northwood’s current API expectations.
4. Friendly names are an app feature. The game supplies the displayed server name; we store a local copy so the user can select it later.
