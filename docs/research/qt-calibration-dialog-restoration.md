# Qt calibration dialog restoration bug

Date: 2026-08-24
Scope: `gui.py` in this repository, PySide6 6.11.2 / Qt 6.11.2 on Windows

## Conclusion

The calibration flow is built on a Qt lifecycle contradiction: it opens `CalibrationDialog` with `QDialog.exec()` and then deliberately calls `hide()` on that same dialog during every capture. In Qt 6.11, hiding a dialog while `exec()` is running explicitly exits the dialog's private event loop. Therefore the modal session ends on the first countdown, before the cursor is read and before `self.index` advances.

The later timer callback attempts to show the same dialog again, but it is no longer inside the `exec()` lifecycle that launched it. Windows may also refuse the subsequent foreground request because SCP:SL became the foreground application. This combination explains both reported outcomes: the window can return without becoming accessible, or the workflow can appear stuck even if its Python state later changes.

The robust design is a persistent, modeless calibration controller plus a system-wide Windows hotkey. The game stays foreground; the user hovers a control and presses the hotkey; the app reads the global cursor position and advances. Neither the parent nor the calibration UI needs a hide/restore cycle.

## Current failure sequence

The relevant repository flow is:

1. `MainWindow.calibrate()` constructs a temporary `CalibrationDialog(self)` and immediately calls `exec()` (`gui.py:407-408`).
2. The dialog also calls `setModal(True)` (`gui.py:60`). `exec()` is modal regardless of this property, and Qt documents `exec()` as a nested event loop that should generally be avoided in favor of asynchronous `open()`.[^qdialog]
3. On capture, `_countdown(3)` calls both `self.app.hide()` and `self.hide()` (`gui.py:118-119`).
4. Qt's 6.11 implementation of `QDialogPrivate::setVisible(false)` calls `eventLoop->exit()` specifically to exit a modal event loop when the dialog is hidden.[^qdialog-source]
5. Consequently, `CalibrationDialog(...).exec()` returns at the first hide. It does not wait for the remaining countdown, `QCursor.pos()`, or `self.index += 1`.
6. Approximately three seconds later, a timer reads the cursor, shows the parent, and calls `showNormal()`, `raise_()`, `activateWindow()`, and `setFocus()` on the dialog (`gui.py:122-134`). This is now a second visibility phase after the original modal execution has already ended.

This is not only theoretical. The following minimal reproduction was run with the project's installed PySide6 6.11.2:

```powershell
py -3.13 -c "import time; from PySide6.QtCore import QTimer; from PySide6.QtWidgets import QApplication,QDialog; app=QApplication([]); d=QDialog(); QTimer.singleShot(75,d.hide); t=time.perf_counter(); result=d.exec(); print(f'exec_result={result} visible={d.isVisible()} elapsed_ms={(time.perf_counter()-t)*1000:.0f}')"
```

Result:

```text
exec_result=0 visible=False elapsed_ms=81
```

The `exec()` call returned immediately after `hide()`, not after the calibration operation completed.

## Why restoration is unreliable on Windows

`raise_()`, `activateWindow()`, and `setFocus()` do not provide a reliable foreground handoff after the user has moved into SCP:SL:

- Qt states that `activateWindow()` does not make a Qt window active on Windows when another application is currently active; Windows instead uses taskbar attention behavior.[^qwidget]
- Microsoft documents that `SetForegroundWindow` is restricted and may be denied even when its listed conditions appear to be satisfied. An application cannot force itself to the foreground while the user is working in another application.[^foreground]
- `setFocus()` only gives a widget keyboard focus when its window is active; otherwise the focus is deferred until activation.[^qwidget]
- `WindowStaysOnTopHint` is a z-order hint, not permission to take foreground activation or keyboard focus.[^window-flags]

The restored dialog remains application-modal because `setModal(True)` is set. If it is visible but not foreground-accessible, the main window can remain blocked by a dialog the user cannot comfortably interact with. This matches the reported "comes back but cannot go to the next step" behavior.

There is another lifecycle mismatch: Qt documents that hiding a `QDialog` does not emit `finished()`, `accepted()`, or `rejected()`.[^qdialog] The caller therefore receives no normal completion signal even though the nested `exec()` loop has exited in Qt's implementation.

## Why the existing test passes

The calibration test committed at `HEAD` (`3390a6d`), `tests/test_gui_flow.py::test_calibration_explains_and_captures_four_points`, passed in 0.21 seconds, but it cannot detect this bug:

- It constructs `CalibrationDialog` directly and never calls `dialog.exec()`.
- It replaces every one-second `QTimer.singleShot` with an immediate callback, so the entire countdown and restoration run synchronously in one Python call stack.
- It never transfers the real Windows foreground to another process.
- `dialog.isVisible()` tests Qt's requested visibility state, not whether Windows made the dialog foreground-accessible.

The test covers coordinate storage and label progression, but not the modal event-loop exit or the native Windows focus handoff that fails for the user.

## Safer UX patterns

### Recommended: modeless overlay plus global hotkey

1. Keep a persistent calibration controller owned by `MainWindow`; do not create it as a temporary `CalibrationDialog(...).exec()` expression.
2. Display a compact modeless tool/overlay with `show()` (or asynchronous `open()` where modality is genuinely needed). Do not hide the main window and do not run a nested dialog event loop.[^qdialog]
3. Register a configurable system-wide capture shortcut with Win32 `RegisterHotKey`, using `MOD_NOREPEAT`. Windows posts `WM_HOTKEY` to the registered window or thread even while SCP:SL has focus.[^register-hotkey][^wm-hotkey]
4. The user hovers the requested game control and presses the shortcut. On `WM_HOTKEY`, read `QCursor.pos()` or `GetCursorPos`, store the point, and advance the state machine immediately.
5. Confirm capture through the always-visible overlay, a sound, or a Windows notification. Do not depend on pulling focus back from the game.
6. Unregister the hotkey when calibration completes or is cancelled. Detect registration failure and let the user choose another key. Do not use F12, which Microsoft reserves for the debugger.[^register-hotkey]

This works because both Qt and Win32 expose the cursor in global screen coordinates; neither API requires the calibration window to be foreground or hidden.[^qcursor][^getcursorpos]

A small informational overlay may use `WindowStaysOnTopHint`. If it must never intercept the game's input, Qt also provides `WindowDoesNotAcceptFocus` and `WindowTransparentForInput`; those flags should be applied only to a display-only overlay, not to the window containing interactive setup controls.[^window-flags]

### Qt-only fallback: visible modeless countdown

If native hotkey registration is not desired, retain a small, movable modeless window and start a countdown without hiding any window. `QCursor.pos()` can still capture the global position after the delay. The user can move the calibration window away from the target control. This is less convenient than a global hotkey but avoids every modal hide/restore failure identified above.[^qcursor]

### If hide/restore must remain

At minimum, the flow would need to stop using `exec()`, retain a durable dialog/controller reference, use asynchronous signals for state transitions, and treat Windows activation as best-effort only. A hidden timer callback should use the `QTimer.singleShot(..., context, functor)` overload so it is cancelled if its owning QObject is destroyed.[^qtimer]

Even with those safeguards, a restore-based design cannot guarantee foreground activation on Windows. The UX must tolerate the app remaining in the background and ask the user to activate it, for example by flashing the taskbar, rather than assuming `activateWindow()` succeeded.

## Root-cause confidence

1. **Confirmed:** `self.hide()` exits the `QDialog.exec()` event loop on the first calibration step. Verified in Qt source and by the local 81 ms reproduction.
2. **Confirmed platform limitation:** Windows can deny the attempted foreground restoration; Qt documents this exact limitation.
3. **Confirmed test gap:** the existing test never executes the modal/native path and therefore cannot regress this failure.
4. **Secondary risk:** the temporary dialog expression and context-free timer callbacks make object lifetime and cancellation harder to reason about after `exec()` unexpectedly returns. This is not required to explain the primary failure.

## Primary sources

[^qdialog]: Qt, [QDialog Class](https://doc.qt.io/qt-6/qdialog.html) and Qt for Python, [PySide6.QtWidgets.QDialog](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDialog.html).
[^qdialog-source]: Qt Project, [`qdialog.cpp` at Qt 6.11.0](https://github.com/qt/qtbase/blob/v6.11.0/src/widgets/dialogs/qdialog.cpp). `QDialog::exec()` creates the local event loop; `QDialogPrivate::setVisible(false)` calls `eventLoop->exit()`.
[^qwidget]: Qt for Python, [PySide6.QtWidgets.QWidget](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html), sections `activateWindow()` and `setFocus()`.
[^foreground]: Microsoft, [SetForegroundWindow function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow).
[^window-flags]: Qt, [Qt::WindowType](https://doc.qt.io/qt-6/qt.html#WindowType-enum).
[^register-hotkey]: Microsoft, [RegisterHotKey function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey).
[^wm-hotkey]: Microsoft, [WM_HOTKEY message](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-hotkey).
[^qcursor]: Qt for Python, [PySide6.QtGui.QCursor](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QCursor.html), `pos()`.
[^getcursorpos]: Microsoft, [GetCursorPos function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getcursorpos).
[^qtimer]: Qt, [QTimer Class](https://doc.qt.io/qt-6/qtimer.html), context-bound `singleShot` overload.
