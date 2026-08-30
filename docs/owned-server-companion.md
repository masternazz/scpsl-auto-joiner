# Owned-server companion

The companion is optional and intended only for SCP:SL servers you own or are
authorized to administer. It exposes one read-only endpoint:

`GET /v1/status`

Requests use a bearer token. Keep remote deployments behind owner-managed
HTTPS; plain HTTP is accepted only for localhost testing. The desktop client
uses a short timeout and falls back to A2S status and ordinary connection
detection when the companion is unavailable.

The desktop profile editor accepts the companion URL and token. On Windows the
token is stored with DPAPI and is not included in server exports, Discord
presence, logs, or the visible server list. A companion result is preferred for
capacity and round data; if it cannot be reached, the app uses the normal A2S
query instead.

The contract may include server name/version, round phase, capacity, and the
current authorized player's role/team. It does not expose player lists, IPs,
Remote Admin credentials, inventory, health, or position. The companion must
be installed separately on the server and is never auto-installed by the app.
