# Unity background-input research

Date: 2026-08-27

## Findings

SCP:SL is running Unity `6000.0.43f1` and reports `Input System module state
changed to: Initialized` in the local `Player.log`. The current Automatic mode
posts `WM_MOUSE*`, `WM_KEY*`, and `WM_CHAR` messages to the SCP:SL window.

Unity's Input System documents that background behavior is controlled by the
game's own `Application.runInBackground` and `InputSettings.backgroundBehavior`
settings. `IgnoreFocus` can process input while unfocused, but that is a setting
inside the Unity project; an external tool cannot enable it in a compiled game.
[Unity InputSettings](https://docs.unity3d.com/Packages/com.unity.inputsystem@1.4/api/UnityEngine.InputSystem.InputSettings.html)

Unity also documents that a device can run in the background only when the
device/backend supports it, and that this behavior varies by platform and
device. This does not promise that posted window messages will be interpreted
as Unity Input System events.
[Unity InputDevice](https://docs.unity3d.com/Packages/com.unity.inputsystem@1.4/api/UnityEngine.InputSystem.InputDevice.html)

Microsoft documents that `PostMessage` only places a message in the target
thread's queue. It does not synthesize hardware/raw-input events. Microsoft
documents separately that raw input arrives as `WM_INPUT`, and background raw
input requires the receiving application to register the device with
`RIDEV_INPUTSINK`.
[PostMessage](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew),
[WM_INPUT](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-input),
[Raw Input overview](https://learn.microsoft.com/en-us/windows/win32/inputdev/about-raw-input)

`SendInput` injects into the system keyboard/mouse input stream and is subject
to UIPI. It does not provide a supported way to direct input to an arbitrary
unfocused Unity window. It therefore requires the target game to be foreground
for reliable mouse/keyboard interaction.
[SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)

## Practical options

1. **Background window messages:** already implemented, but SCP:SL's current
   Unity client has demonstrated that it ignores this path. Activation messages
   do not change that limitation.
2. **Background raw input / virtual HID:** only viable if SCP:SL registers its
   keyboard/mouse devices for background raw input. The external tool cannot
   force that registration. Installing a kernel-level input driver would add
   security and compatibility risks and is not an appropriate default.
3. **Temporary foreground input:** the reliable supported desktop path. The
   tool can focus SCP:SL only for the short click/type sequence, restore the
   prior cursor/window immediately, and remain hands-off while waiting.
4. **In-process plugin or game modification:** could configure Unity input from
   inside the client, but is outside the scope of a safe external utility and
   could violate game/server rules.

## Conclusion

For this compiled SCP:SL client, a guaranteed “game interacts while fully
unfocused and the user keeps the mouse/keyboard” mode is not available through
ordinary external Windows messages. The honest reliable design is a clearly
labelled temporary-foreground mode, plus a best-effort background mode with
diagnostics. No release should claim that background mode is reliable until a
private-server test proves it on the user's exact client build.
