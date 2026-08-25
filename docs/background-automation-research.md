# Background Direct Connect automation for SCP:SL on Windows

Research date: 2026-08-25. This report uses only first-party Northwood/SCP:SL, Valve/Steamworks, Microsoft, and Unity documentation. **Documented** statements come directly from those sources; **inference** labels conclusions that still require testing against the installed game.

## Recommendation

Use SCP:SL's documented Steam Direct Connect entry point, not simulated mouse or keyboard input:

- `steam://connect/IP:Port`
- `+connect IP:Port` as a game launch argument

Northwood explicitly documents both mechanisms and fixed their authentication timing in SCP:SL 14.1.4. This is the only reviewed route that asks the game to connect at the application level instead of driving its rendered menu. [Northwood 14.1.4 technical changes](https://en.scpslgame.com/index.php?title=Updates/14.1.4)

For an already-running game, Valve documents that a game can receive new command-line parameters from a `steam://run/<appid>//<command line>/` URL through `NewUrlLaunchParameters_t`. SCP:SL's Steam App ID is 700330. [Steamworks `ISteamApps::GetLaunchCommandLine` and `NewUrlLaunchParameters_t`](https://partner.steamgames.com/doc/api/ISteamApps?l=english), [official SCP:SL Steam page](https://store.steampowered.com/app/700330/SCP_Secret_Laboratory/)

That makes the following a second candidate for controlled testing:

```text
steam://run/700330//+connect%20IP%3APort/
```

**Inference:** Northwood's documented `+connect` handler combined with Valve's documented running-game URL callback should let Steam deliver a retry to the existing SCP:SL process without mouse or keyboard input. The first test should still use Northwood's exact `steam://connect/IP:Port` form. Neither Northwood nor Valve promises that invoking either URI will leave every window's foreground state unchanged, so no-focus behavior must be verified on the target PC before this replaces the current foreground method.

## Comparison

| Method | Physical input / focus | Unity and SCP:SL fit | Reliability and policy assessment |
|---|---|---|---|
| `steam://connect/IP:Port` | Does not synthesize mouse or keyboard input; foreground behavior is not guaranteed in the cited docs | Explicitly supported by Northwood | **Best first choice.** First-party and least invasive; validate repeated calls while SCP:SL is already open |
| `steam://run/700330//+connect.../` | Does not synthesize input; Steam delivers parameters through its application API | Northwood documents `+connect`; Valve documents delivery of new URL parameters to a running game | **Strong second choice.** The combination is a well-supported inference, but exact SCP:SL runtime behavior still needs a live test |
| `PostMessage` with `WM_KEY*`/`WM_MOUSE*` | Can target an HWND without moving the cursor or globally typing | Weak fit: it only queues Win32 messages, while Unity input may be focus-gated or use raw/device input | **Experimental only.** A successful API return proves queuing, not that Unity accepted a click |
| `SendMessage` | Targeted and does not move the cursor, but synchronously enters the target window procedure | Same input-path uncertainty as `PostMessage` | **Avoid for retries.** It can block until the game thread processes the message |
| Microsoft UI Automation | Does not inherently synthesize physical input; a provider can still choose to change focus | Works only if SCP:SL exposes its custom-rendered controls as UIA elements and patterns | **Safe to inspect, unlikely to be complete.** Use only if the address field exposes `Value` and Connect exposes `Invoke` |
| Client console `rc` / `reconnect` | Entering it normally requires keyboard focus | Official client command, but it reconnects the last server rather than supplying a selected endpoint | **Not suitable for unattended background control** without a separate documented command channel |
| `SendInput`, mouse movement, or global hotkeys | Inserts events into the system input stream and therefore conflicts with the requirement | Reaches ordinary game input only through global/focused input behavior | **Reject.** It can interfere with TikTok or any foreground app |

## Why targeted window messages are brittle

`PostMessage` places a message in the queue belonging to a specified window thread and returns immediately. `SendMessage` calls the target window procedure and waits for it to process the message. Both are limited by Windows User Interface Privilege Isolation (UIPI), so a lower-integrity auto-joiner cannot message a higher-integrity game. [Microsoft `PostMessageW`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew), [Microsoft `SendMessageW`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendmessagew)

Windows documents `WM_KEYDOWN` as a message posted to the window that has keyboard focus. Posting a look-alike message directly to an unfocused HWND bypasses normal routing, but it does not create actual device state or prove that the receiving engine treats it as input. [Microsoft `WM_KEYDOWN`](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-keydown)

Windows Raw Input is a separate path: the target registers devices, receives `WM_INPUT`, and reads an opaque `HRAWINPUT` handle supplied by the system. Background raw input requires explicit `RIDEV_INPUTSINK` registration. A normal `PostMessage(WM_INPUT, ...)` cannot manufacture a valid raw-input record. [Microsoft Raw Input overview](https://learn.microsoft.com/en-us/windows/win32/inputdev/about-raw-input), [Microsoft `WM_INPUT`](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-input)

Unity's newer Input System also treats focus as part of input delivery. Its default background behavior resets and disables devices that cannot run in the background, and Unity says background-capable device input is uncommon outside select hardware/platform combinations. [Unity `InputSettings.backgroundBehavior`](https://docs.unity3d.com/Packages/com.unity.inputsystem@1.4/api/UnityEngine.InputSystem.InputSettings.html), [Unity `InputDevice.canRunInBackground`](https://docs.unity3d.com/Packages/com.unity.inputsystem@1.4/api/UnityEngine.InputSystem.InputDevice.html)

**Inference:** because Northwood does not publish SCP:SL's exact client input backend or any Win32 message contract for Direct Connect, targeted `WM_LBUTTON*`, `WM_CHAR`, or `WM_KEY*` sequences are version-sensitive and should not be the default. `PostMessage` is preferable to `SendMessage` for a one-shot diagnostic because it cannot block the caller on the game thread, but neither is likely to be as reliable as the supported Steam connection route.

## Why UI Automation is unlikely to solve it

UI Automation can cleanly call `Invoke` on a button or set a field through `Value`, but only when the target exposes the corresponding provider and control pattern. Microsoft states that custom controls need UIA providers; without a provider or proxy, a custom control is largely opaque beyond basic HWND information. [Microsoft UI Automation providers overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-providersoverview), [Microsoft UI Automation control patterns](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpatternsoverview)

**Inference:** SCP:SL's Unity-rendered server browser is likely exposed as one game window rather than native Edit and Button controls. UIA is worth a read-only inspection with Microsoft's Accessibility Insights/Inspect tooling, but it should be rejected if the Direct Connect field lacks `ValuePattern` or the Connect button lacks `InvokePattern`. Do not replace missing patterns with `SetFocus` or `SendKeys`, because that restores the exact foreground-input problem.

## Console and launch options

Northwood's current launch-options reference lists many SCP:SL and Unity arguments, but the decisive Direct Connect documentation is the 14.1.4 update note: `steam://connect/IP:Port` and `+connect` are supported connection paths. [Northwood client/server launch options](https://techwiki.scpslgame.com/books/common-debugging-steps/page/client-server-launch-options-for-scp-secret-laboratory), [Northwood 14.1.4](https://en.scpslgame.com/index.php?title=Updates/14.1.4)

Northwood also documented the client console aliases `rc` and `reconnect` for rejoining the last server. No reviewed first-party source documents a separate external console IPC/API that another desktop process can call in the background. [Northwood 9.0.3 update notes](https://en.scpslgame.com/index.php?title=Updates/9.0.3)

## Anti-cheat boundary

SCP:SL runs its anti-cheat in online mode. Northwood's EULA forbids modifying or interfering with the online game process, reverse engineering or bypassing anti-cheat, and intercepting or redirecting game network traffic. [Northwood SCP:SL EULA](https://store.steampowered.com/eula/700330_eula_0)

The documented Steam URI/launch-argument route is therefore the safest option: it uses a feature Northwood intentionally supports and does not inject into the process, patch memory, hook input, emulate a driver, or construct/intercept game network traffic. UIA and ordinary window messages are external OS APIs, but Northwood does not explicitly approve this auto-join use. If the tool will be distributed, obtaining written confirmation from Northwood is prudent. Do not pursue DLL injection, memory reading/writing, private-message discovery by reverse engineering, network packet replay, or anti-cheat workarounds.

## Safe validation plan

1. Test on an account and server where repeated connection attempts are authorized. Leave SCP:SL open at its menu in borderless mode and keep another harmless app focused.
2. Record the foreground HWND and cursor position, invoke one `steam://connect/IP:Port` URI, then verify that both remain unchanged. Use `Player.log` only to confirm that SCP:SL attempted the endpoint and later joined or received a full/rejection result.
3. Repeat with SCP:SL unfocused and then minimized. Treat these as separate cases; a background callback may work while a minimized Unity player behaves differently.
4. If the exact `steam://connect` URI steals focus or cannot retrigger the running client, test one URL-encoded `steam://run/700330//+connect%20IP%3APort/` request and verify Valve's running-game callback behavior empirically.
5. Retry only after the prior attempt has produced a definitive joined/rejected log result. Use the configured backoff (for example, two seconds after a full-server rejection) and avoid flooding Steam or the game server.
6. Stop immediately on an anti-cheat warning, kick, crash, unexpected foreground activation, or input interference. Keep the existing foreground method as an opt-in fallback until the URI route passes repeated tests across supported SCP:SL versions.

## Bottom line

The research changes the preferred design: **do not click the Unity menu in the background. Send SCP:SL its officially supported Direct Connect request through Steam.** This is much more likely to preserve the user's mouse, keyboard, and foreground app. It still needs a small live compatibility test because the official sources do not guarantee non-activation behavior or repeated URI handling on every Steam/Windows setup.
