# SCP:SL Auto-Joiner LabAPI companion

This is a separate, owner-installed server plugin. It is not loaded by the
desktop application and is never installed into a client game directory.

The project targets the current official LabAPI source. Set `SL_REFERENCES` to
the server's `SCPSL_Data/Managed` directory, then build with:

```powershell
dotnet build -c Release
```

Copy the resulting DLL to the server's LabAPI plugins directory. Configure the
listener token with `SCP_SL_AUTOJOINER_COMPANION_TOKEN` (at least 32
characters) and, if personal role data is wanted, set
`SCP_SL_AUTOJOINER_ALLOWED_STEAM_IDS` to a comma-separated list of Steam IDs.
The plugin binds to loopback HTTP only. Remote use requires an owner-managed
HTTPS reverse proxy; the desktop client rejects remote HTTP.

The endpoint is `GET /v1/status` and returns only server identity, round phase,
capacity, and the requesting player's role when that Steam ID is allowlisted.
It never returns a player list, credentials, inventory, health, position, or IP
addresses.

The plugin is intentionally built separately from the desktop application. A
matching `Assembly-CSharp.dll` and `LabAPI.dll` from the target server must be
available through `SL_REFERENCES`; the desktop build does not bundle or fake
those server assemblies.
