"""Crisp, DPI-aware Qt desktop UI for the SCP:SL Auto-Joiner."""
import os
import threading

# Set the process coordinate system before Qt creates any windows. Native
# calibration and Win32 clicks then agree even at 150/200/250% scaling.
import winput
winput.set_dpi_awareness()

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFrame, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QProgressBar, QScrollArea, QSizePolicy, QSpacerItem, QStackedWidget,
    QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

import config as config_mod
import joiner
import logwatch
import resolver
from app_paths import resource_path

BG = "#0b0f14"
SURFACE = "#121820"
CARD = "#18222d"
CARD_HOVER = "#202d3b"
LINE = "#2b3947"
TEXT = "#edf3f7"
MUTED = "#91a4b2"
SUBTLE = "#667786"
CYAN = "#54d7f4"
AMBER = "#ffb74d"
GREEN = "#68d391"
RED = "#ef8585"


class Bridge(QObject):
    status = Signal(str)
    busy = Signal(bool)
    saved = Signal(str, str)


def label(text, style="body"):
    widget = QLabel(text)
    widget.setProperty("role", style)
    widget.setWordWrap(True)
    widget.setMinimumWidth(0)
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return widget


class CalibrationOverlay(QWidget):
    def __init__(self):
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
        super().__init__(None, flags)
        self.setObjectName("calibrationOverlay")
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMinimumWidth(560)
        self.setStyleSheet(f"QWidget#calibrationOverlay {{ background: {BG}; border: 1px solid {CYAN}; border-radius: 8px; }}")
        box = QVBoxLayout(self)
        box.setContentsMargins(20, 14, 20, 14)
        self.message = label("", "section")
        box.addWidget(self.message)

    def show_on(self, screen):
        self.adjustSize()
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 24, area.top() + 24)
        self.show()
        self.raise_()


class CalibrationDialog(QDialog):
    steps = [("servers_tab", "Servers tab"), ("direct_connect", "Direct Connect button"), ("ip_field", "IP/Hostname field"), ("connect_button", "Connect button")]

    def __init__(self, app):
        super().__init__(app)
        self.app, self.index = app, 0
        self.active = False
        self.overlay = None
        self.cfg = config_mod.load_config()
        self.setWindowTitle("Calibrate controls")
        self.setMinimumSize(560, 360)
        self.resize(620, 430)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(14)
        layout.addWidget(label("Calibrate controls", "title"))
        layout.addWidget(label("Start once, hover each named SCP:SL control, and press F8. The guide advances automatically through all four controls."))
        self.progress = QProgressBar()
        self.progress.setRange(0, len(self.steps))
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.step_label = label("", "section")
        layout.addWidget(self.step_label)
        self.instructions = label("Hover the control named in the guide and press F8. You do not click the game or return here between steps.", "body")
        layout.addWidget(self.instructions)
        layout.addWidget(label("F8 captures the mouse position. F9 cancels and returns to the app.", "warning"))
        layout.addStretch()
        row = QHBoxLayout()
        self.capture_button = QPushButton("Begin guided calibration")
        self.capture_button.setProperty("kind", "primary")
        self.capture_button.clicked.connect(self.begin_calibration)
        row.addWidget(self.capture_button)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.cancel_calibration)
        row.addWidget(cancel)
        layout.addLayout(row)
        self.hotkey_timer = QTimer(self)
        self.hotkey_timer.setInterval(40)
        self.hotkey_timer.timeout.connect(self.poll_hotkeys)
        self.f8_down = self.f9_down = False
        self.show_step()

    def show_step(self):
        _, title = self.steps[self.index]
        self.step_label.setText(f"Step {self.index + 1} of {len(self.steps)}  ·  {title}")
        self.progress.setValue(self.index)

    def begin_calibration(self):
        if self.active:
            return
        self.active = True
        self.overlay = CalibrationOverlay()
        self.app.hide()
        self.hide()
        self.update_overlay()
        self.overlay.show_on(self.app.screen() or QApplication.primaryScreen())
        self.hotkey_timer.start()

    def update_overlay(self):
        _, title = self.steps[self.index]
        self.overlay.message.setText(
            f"CALIBRATION  ·  Step {self.index + 1} of {len(self.steps)}\n"
            f"Hover: {title}    •    Press F8 to capture    •    F9 to cancel"
        )

    def poll_hotkeys(self):
        f8 = winput.key_is_down(winput.VK_F8)
        f9 = winput.key_is_down(winput.VK_F9)
        if f8 and not self.f8_down:
            self.capture_current_point()
        elif f9 and not self.f9_down:
            self.cancel_calibration()
        self.f8_down, self.f9_down = f8, f9

    def capture_current_point(self):
        if not self.active or self.index >= len(self.steps):
            return
        point = winput.get_cursor_pos()
        if point is None:
            self.overlay.message.setText("Could not read the mouse position. Move the mouse and press F8 again.")
            return
        name, _ = self.steps[self.index]
        self.cfg["click_points"][name] = [int(point[0]), int(point[1])]
        self.index += 1
        self.progress.setValue(self.index)
        if self.index < len(self.steps):
            self.update_overlay()
        else:
            self.finish_calibration()

    def finish_calibration(self):
        self.hotkey_timer.stop()
        self.overlay.close()
        self.active = False
        self.cfg["navigation_mode"] = "manual"
        self.cfg["calibration_space"] = "physical_v2"
        config_mod.save_config(self.cfg)
        self.app.refresh()
        self.app.bridge.status.emit("Manual calibration saved and active.")
        self.app.show()
        self.app.raise_()
        self.app.activateWindow()
        self.accept()

    def cancel_calibration(self):
        if self.active:
            self.hotkey_timer.stop()
            self.overlay.close()
            self.active = False
            self.app.show()
            self.app.raise_()
            self.app.activateWindow()
        self.reject()


class HelpDialog(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.setWindowTitle("How SCP:SL Auto-Joiner works")
        self.setMinimumSize(600, 480)
        self.resize(720, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.addWidget(label("How it works", "title"))
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            "1. Automatic mode\n\n"
            "By default, the app scales clicks to SCP:SL's current window. Different resolutions and borderless fullscreen layouts normally need no calibration.\n\n"
            "2. Optional calibration\n\n"
            "If automatic navigation misses a control, use Calibrate controls. Start once, hover each requested game control, and press F8. The on-screen guide advances through all four steps automatically. F9 cancels.\n\n"
            "3. Remember a server\n\n"
            "Join normally and click Remember a server. The app reads the IP and port from Player.log and saves the endpoint.\n\n"
            "4. Start auto-join\n\n"
            "Choose the saved server. The app launches SCP:SL if needed, opens Direct Connect, enters the endpoint, and retries rejected joins.\n\n"
            "5. Safety\n\n"
            "It does not read memory, use OCR, modify packets, or bypass anti-cheat. It sends normal Windows input and watches Player.log."
        )
        layout.addWidget(text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.bridge = Bridge()
        self.bridge.status.connect(self.status_text)
        self.bridge.busy.connect(self.set_busy)
        self.bridge.saved.connect(self.server_saved)
        self.busy = False
        self.stop_event = threading.Event()
        self.servers = {}
        self.setWindowTitle("SCP:SL Auto-Joiner")
        self.setMinimumSize(760, 560)
        self.resize(1180, 760)
        self.setWindowIcon(QIcon(resource_path("assets/app.ico")))
        self.build()
        self.refresh()

    def build(self):
        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(22, 26, 18, 22)
        side.setSpacing(8)
        brand_row = QHBoxLayout()
        mark = QLabel("S")
        mark.setObjectName("brandMark")
        mark.setAlignment(Qt.AlignCenter)
        brand_row.addWidget(mark)
        brand = QVBoxLayout()
        brand.addWidget(label("SCP:SL", "brand"))
        brand.addWidget(label("AUTO-JOINER", "brandSub"))
        brand_row.addLayout(brand)
        side.addLayout(brand_row)
        rule = QFrame(); rule.setFrameShape(QFrame.HLine); rule.setObjectName("rule"); side.addWidget(rule); side.addSpacing(18)
        side.addWidget(label("CONTAINMENT OPERATIONS", "eyebrow"))
        self.join_nav = QPushButton("01   Auto-Join")
        self.setup_nav = QPushButton("02   Calibration")
        self.settings_nav = QPushButton("03   Settings")
        self.help_nav = QPushButton("04   How it works")
        for button in (self.join_nav, self.setup_nav, self.settings_nav, self.help_nav):
            button.setProperty("kind", "nav")
            side.addWidget(button)
        self.join_nav.clicked.connect(lambda: self.show_page(0))
        self.setup_nav.clicked.connect(lambda: self.show_page(1))
        self.settings_nav.clicked.connect(lambda: self.show_page(2))
        self.help_nav.clicked.connect(lambda: self.show_page(3))
        side.addStretch()
        side.addWidget(label("LOCAL DESKTOP TOOL", "eyebrow"))
        side.addWidget(label("Servers and calibration stay on this computer.", "sideNote"))
        shell_layout.addWidget(sidebar)

        self.pages = QStackedWidget()
        self.pages.addWidget(self.join_page())
        self.pages.addWidget(self.setup_page())
        self.pages.addWidget(self.settings_page())
        self.pages.addWidget(self.help_page())
        shell_layout.addWidget(self.pages, 1)
        self.setCentralWidget(shell)
        self.show_page(0)

    def scroll_page(self, content):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    def page_content(self):
        content = QWidget()
        content.setObjectName("page")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(46, 42, 46, 54)
        layout.setSpacing(16)
        return content, layout

    def heading(self, layout, eyebrow, title, description):
        layout.addWidget(label(eyebrow, "eyebrow"))
        layout.addWidget(label(title, "pageTitle"))
        description_label = label(description, "lede")
        description_label.setMaximumWidth(760)
        layout.addWidget(description_label)
        layout.addSpacing(14)

    def card(self):
        frame = QFrame(); frame.setObjectName("card")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(frame); layout.setContentsMargins(26, 24, 26, 24); layout.setSpacing(10)
        return frame, layout

    def join_page(self):
        content, layout = self.page_content()
        self.heading(layout, "CONTAINMENT OPERATIONS  /  READY", "Auto-Join", "Keep trying until a slot opens. The app drives Direct Connect and watches SCP:SL's own log for the result.")
        destination, box = self.card()
        box.addWidget(label("DESTINATION", "eyebrow"))
        box.addWidget(label("Choose a saved server", "section"))
        box.addWidget(label("Saved names stay local and can be reused whenever you play.", "body"))
        box.addSpacing(8)
        box.addWidget(label("SERVER NAME", "fieldLabel"))
        self.server_box = QComboBox(); self.server_box.setEditable(True); self.server_box.setInsertPolicy(QComboBox.NoInsert); self.server_box.setPlaceholderText("Start typing a saved server…")
        self.server_box.lineEdit().textEdited.connect(self.filter_servers)
        self.server_box.currentTextChanged.connect(self.update_endpoint_preview)
        box.addWidget(self.server_box)
        self.endpoint_preview = label("No saved server selected.", "helper")
        box.addWidget(self.endpoint_preview)
        self.join_button = QPushButton("Start auto-join"); self.join_button.setProperty("kind", "primary")
        self.remember_button = QPushButton("Remember a server")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.join_button.clicked.connect(self.join); self.remember_button.clicked.connect(self.remember)
        self.stop_button.clicked.connect(self.stop_join)
        box.addWidget(self.join_button)
        secondary_actions = QHBoxLayout(); secondary_actions.setSpacing(10)
        secondary_actions.addWidget(self.remember_button); secondary_actions.addWidget(self.stop_button); secondary_actions.addStretch()
        box.addLayout(secondary_actions)
        box.addWidget(label("Remember a server watches your next normal connection, detects its IP and port, then asks you to give it a friendly name.", "helper"))
        layout.addWidget(destination)
        activity, activity_box = self.card()
        row = QHBoxLayout(); row.addWidget(label("LIVE FEED", "eyebrow")); row.addStretch(); self.feed = label("IDLE", "pill"); row.addWidget(self.feed); activity_box.addLayout(row)
        self.status = label("Ready. Choose a server and start. Automatic controls are enabled.", "status")
        activity_box.addWidget(self.status)
        self.progress = QProgressBar(); self.progress.setRange(0, 0); self.progress.hide(); activity_box.addWidget(self.progress)
        layout.addWidget(activity)
        layout.addStretch()
        return self.scroll_page(content)

    def setup_page(self):
        content, layout = self.page_content()
        self.heading(layout, "OPTIONAL FALLBACK  /  LOCAL", "Calibration", "Automatic window-relative clicks are used first. Capture four controls only if your display needs a manual fallback.")
        card, box = self.card()
        box.addWidget(label("CONTROL SETUP", "eyebrow"))
        box.addWidget(label("Calibrate this computer", "section"))
        box.addWidget(label("Start one guided session, hover Servers, Direct Connect, the IP/Hostname field, and Connect in order, and press F8 for each. The guide advances automatically; F9 cancels.", "body"))
        row = QHBoxLayout(); self.calibration_status = label("Automatic window-relative controls enabled.", "warning"); row.addWidget(self.calibration_status); row.addStretch(); box.addLayout(row)
        button = QPushButton("Open calibration")
        button.setProperty("kind", "primary"); button.clicked.connect(self.calibrate); box.addWidget(button)
        layout.addWidget(card)
        info, info_box = self.card(); info_box.addWidget(label("WHY THIS EXISTS", "eyebrow")); info_box.addWidget(label("Two navigation modes", "section")); info_box.addWidget(label("Automatic mode scales to the current SCP:SL window. Manual mode is a precise per-computer fallback when a display or game layout behaves differently.", "body")); layout.addWidget(info); layout.addStretch()
        return self.scroll_page(content)

    def settings_page(self):
        content, layout = self.page_content()
        self.heading(layout, "LOCAL CONFIGURATION  /  ADVANCED", "Settings", "Tune retry behavior and inspect the exact native-pixel coordinates used on this computer.")

        controls, box = self.card()
        box.addWidget(label("NAVIGATION", "eyebrow"))
        box.addWidget(label("Control mode", "section"))
        box.addWidget(label("Automatic scales with the SCP:SL window. Manual uses the four physical screen positions captured by calibration.", "body"))
        self.navigation_mode = QComboBox()
        self.navigation_mode.addItem("Automatic — window-relative (recommended)", "automatic")
        self.navigation_mode.addItem("Manual — calibrated physical pixels", "manual")
        self.navigation_mode.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.navigation_mode.setMinimumContentsLength(12)
        self.navigation_mode.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        box.addWidget(self.navigation_mode)
        self.settings_feedback = label("", "helper")
        box.addWidget(self.settings_feedback)
        layout.addWidget(controls)

        timing, timing_box = self.card()
        timing_box.addWidget(label("RETRY LIMITS", "eyebrow"))
        timing_box.addWidget(label("Timing and stop conditions", "section"))
        timing_box.addWidget(label("The app confirms joined/rejected states from Player.log, so these values do not depend on screen resolution.", "body"))
        timing_grid = QGridLayout(); timing_grid.setHorizontalSpacing(18); timing_grid.setVerticalSpacing(10)
        fields = [
            ("Retry delay", "Seconds between rejected attempts", "retry_interval", 1, 60),
            ("Connection timeout", "Seconds allowed for one attempt", "attempt_timeout", 5, 180),
            ("Maximum attempts", "Stop after this many tries", "max_attempts", 1, 1000),
            ("Maximum runtime", "Stop after this many minutes", "max_minutes", 1, 240),
        ]
        for row, (title, hint, attr, minimum, maximum) in enumerate(fields):
            text_box = QVBoxLayout(); text_box.setSpacing(1); text_box.addWidget(label(title, "body")); text_box.addWidget(label(hint, "helper"))
            timing_grid.addLayout(text_box, row, 0)
            spin = QSpinBox(); spin.setRange(minimum, maximum); spin.setMinimumWidth(130)
            setattr(self, attr, spin); timing_grid.addWidget(spin, row, 1)
        timing_grid.setColumnStretch(0, 1)
        timing_box.addLayout(timing_grid)
        layout.addWidget(timing)

        points, points_box = self.card()
        points_box.addWidget(label("MANUAL COORDINATES", "eyebrow"))
        points_box.addWidget(label("Captured physical pixels", "section"))
        points_box.addWidget(label("These values are resolution-specific. Use guided calibration after changing monitor layout, game resolution, or display scaling; then fine-tune here only if needed.", "body"))
        point_grid = QGridLayout(); point_grid.setHorizontalSpacing(12); point_grid.setVerticalSpacing(8)
        point_grid.addWidget(label("Control", "fieldLabel"), 0, 0)
        point_grid.addWidget(label("X", "fieldLabel"), 0, 1)
        point_grid.addWidget(label("Y", "fieldLabel"), 0, 2)
        self.point_inputs = {}
        for row, (key, title) in enumerate(CalibrationDialog.steps, 1):
            point_grid.addWidget(label(title, "body"), row, 0)
            x_spin = QSpinBox(); y_spin = QSpinBox()
            for spin in (x_spin, y_spin):
                spin.setRange(-32768, 32767); spin.setMinimumWidth(96)
            point_grid.addWidget(x_spin, row, 1); point_grid.addWidget(y_spin, row, 2)
            self.point_inputs[key] = (x_spin, y_spin)
        point_grid.setColumnStretch(0, 1)
        points_box.addLayout(point_grid)
        layout.addWidget(points)

        actions, actions_box = self.card()
        actions_box.addWidget(label("APPLY", "eyebrow"))
        self.save_settings_button = QPushButton("Save settings"); self.save_settings_button.setProperty("kind", "primary")
        self.save_settings_button.clicked.connect(self.save_settings)
        self.automatic_button = QPushButton("Use automatic controls"); self.automatic_button.clicked.connect(self.use_automatic_controls)
        self.settings_calibration_button = QPushButton("Open calibration"); self.settings_calibration_button.clicked.connect(self.calibrate)
        actions_box.addWidget(self.save_settings_button)
        actions_box.addWidget(self.automatic_button)
        actions_box.addWidget(self.settings_calibration_button)
        layout.addWidget(actions)
        layout.addStretch()
        return self.scroll_page(content)

    def help_page(self):
        content, layout = self.page_content()
        self.heading(layout, "FIELD MANUAL  /  REFERENCE", "How it works", "A plain-language guide to every button and what the automation is doing.")
        for number, title, text in [
            ("01", "Automatic first", "Clicks scale to the current SCP:SL window, so different resolutions and borderless fullscreen layouts normally need no setup."),
            ("02", "Optional calibration", "Start once, hover each requested control, and press F8. A click-through guide advances through all four controls automatically; F9 cancels."),
            ("03", "Remember a server", "Start the watcher and join normally. Player.log supplies the endpoint, then the app asks the server directly for its public name and pre-fills the popup."),
            ("04", "Reliable join detection", "Joined and rejected states come from SCP:SL's own Player.log. This is more reliable than OCR across 4K scaling, animations, and UI changes."),
            ("05", "What it does not do", "No memory reading, packet manipulation, OCR, or anti-cheat bypass. It sends normal Windows input and reads Player.log."),
        ]:
            card, box = self.card(); box.addWidget(label(number, "number")); box.addWidget(label(title, "section")); box.addWidget(label(text, "body")); layout.addWidget(card)
        layout.addStretch()
        return self.scroll_page(content)

    def show_page(self, index):
        self.pages.setCurrentIndex(index)
        for button, active in ((self.join_nav, index == 0), (self.setup_nav, index == 1), (self.settings_nav, index == 2), (self.help_nav, index == 3)):
            button.setProperty("active", active); button.style().unpolish(button); button.style().polish(button)

    def refresh(self):
        current = self.server_box.currentText()
        self.servers = resolver.load_servers()
        self.server_box.clear(); self.server_box.addItems(sorted(self.servers))
        if current in self.servers:
            self.server_box.setCurrentText(current)
        self.update_endpoint_preview(self.server_box.currentText())
        cfg = config_mod.load_config(); manual = cfg.get("navigation_mode") == "manual" and config_mod.calibrated(cfg)
        legacy = cfg.get("navigation_mode") == "manual" and not config_mod.calibrated(cfg)
        text = "Manual calibration saved and active." if manual else ("Old DPI-scaled calibration disabled — calibrate once again." if legacy else "Automatic window-relative controls enabled.")
        self.calibration_status.setText(text)
        self.load_settings_form(cfg)

    def load_settings_form(self, cfg):
        if not hasattr(self, "navigation_mode"):
            return
        mode = "manual" if cfg.get("navigation_mode") == "manual" and config_mod.calibrated(cfg) else "automatic"
        self.navigation_mode.setCurrentIndex(self.navigation_mode.findData(mode))
        self.retry_interval.setValue(int(cfg.get("retry_interval_s", config_mod.DEFAULTS["retry_interval_s"])))
        self.attempt_timeout.setValue(int(cfg.get("attempt_timeout_s", config_mod.DEFAULTS["attempt_timeout_s"])))
        self.max_attempts.setValue(int(cfg.get("max_attempts", config_mod.DEFAULTS["max_attempts"])))
        self.max_minutes.setValue(int(cfg.get("max_minutes", config_mod.DEFAULTS["max_minutes"])))
        for key, (x_spin, y_spin) in self.point_inputs.items():
            x, y = cfg["click_points"].get(key, (0, 0))
            x_spin.setValue(int(x)); y_spin.setValue(int(y))
        if cfg.get("navigation_mode") == "manual" and not config_mod.calibrated(cfg):
            self.settings_feedback.setText("Your previous DPI-scaled calibration is disabled. Run calibration once to capture correct 4K physical pixels.")
        else:
            self.settings_feedback.setText("Manual calibration is active." if mode == "manual" else "Automatic window-relative controls are active.")

    def save_settings(self):
        cfg = config_mod.load_config()
        cfg["navigation_mode"] = self.navigation_mode.currentData()
        cfg["retry_interval_s"] = self.retry_interval.value()
        cfg["attempt_timeout_s"] = self.attempt_timeout.value()
        cfg["max_attempts"] = self.max_attempts.value()
        cfg["max_minutes"] = self.max_minutes.value()
        for key, (x_spin, y_spin) in self.point_inputs.items():
            cfg["click_points"][key] = [x_spin.value(), y_spin.value()]
        if cfg["navigation_mode"] == "manual" and not config_mod.calibrated(cfg):
            self.settings_feedback.setText("Manual mode needs a fresh guided calibration before it can be enabled.")
            return
        config_mod.save_config(cfg)
        self.settings_feedback.setText("Settings saved.")
        self.calibration_status.setText("Manual calibration saved and active." if cfg["navigation_mode"] == "manual" else "Automatic window-relative controls enabled.")

    def use_automatic_controls(self):
        cfg = config_mod.load_config()
        cfg["navigation_mode"] = "automatic"
        config_mod.save_config(cfg)
        self.load_settings_form(cfg)
        self.calibration_status.setText("Automatic window-relative controls enabled.")
        self.settings_feedback.setText("Automatic controls enabled and saved.")

    def filter_servers(self, query):
        current = self.server_box.currentText()
        self.server_box.clear(); self.server_box.addItems(sorted(name for name in self.servers if query.lower() in name.lower()) or sorted(self.servers)); self.server_box.setEditText(current)

    def update_endpoint_preview(self, name):
        entry = self.servers.get(name)
        if entry:
            self.endpoint_preview.setText(f"Will join {entry['ip']}:{entry['port']}")
        else:
            self.endpoint_preview.setText("Choose a saved server from the list.")

    def status_text(self, text):
        self.status.setText(text)

    def set_busy(self, busy):
        self.busy = busy; self.join_button.setEnabled(not busy); self.remember_button.setEnabled(not busy); self.progress.setVisible(busy); self.feed.setText("RUNNING" if busy else "IDLE")
        if not busy:
            self.stop_button.setEnabled(False)

    def join(self):
        name = self.server_box.currentText().strip()
        if not name or self.busy: return
        self.stop_event.clear(); self.set_busy(True); self.stop_button.setEnabled(True)
        threading.Thread(target=self.run_join, args=(name,), daemon=True).start()

    def run_join(self, name):
        result = joiner.run(name, on_status=self.bridge.status.emit, stop_event=self.stop_event)
        messages = {"success": "Joined successfully.", "stopped": "Auto-join stopped.", "gave_up": "Stopped after reaching the retry limit.", "unclear": "Stopped because the game returned an unclear result.", "not_found": "That server is not saved yet.", "launch_failed": "SCP:SL could not be started."}
        self.bridge.status.emit(messages.get(result, result)); self.bridge.busy.emit(False)

    def stop_join(self):
        self.stop_event.set()
        self.stop_button.setEnabled(False)
        self.bridge.status.emit("Stopping auto-join...")

    def remember(self):
        if self.busy: return
        self.set_busy(True); threading.Thread(target=self.watch_server, daemon=True).start()

    def watch_server(self):
        try:
            self.bridge.status.emit("Join the server normally in SCP:SL. Reading its connection details...")
            watcher = logwatch.LogWatcher()
            try: match = watcher.wait_for_regex(logwatch.CONNECTING_IP_RE, 120)
            finally: watcher.close()
            if match:
                ip, port = match.group(1), int(match.group(2))
                detected_name = resolver.query_server_name(ip, port) or ""
                self.bridge.saved.emit(f"{ip}:{port}", detected_name)
            else: self.bridge.status.emit("Timed out waiting for a connection attempt."); self.bridge.busy.emit(False)
        except Exception:
            self.bridge.status.emit("Could not watch the SCP:SL log. Is the game installed?"); self.bridge.busy.emit(False)

    def server_saved(self, endpoint, detected_name):
        ip, port = endpoint.rsplit(":", 1)
        suggested = detected_name or f"Saved server {len(self.servers) + 1}"
        details = f"Detected server: {detected_name}\nEndpoint: {endpoint}" if detected_name else f"Detected endpoint: {endpoint}"
        name, accepted = QInputDialog.getText(self, "Name this server", f"{details}\n\nConfirm or edit the friendly name:", QLineEdit.Normal, suggested)
        name = name.strip()
        if not accepted or not name:
            self.bridge.status.emit(f"Detected {endpoint}, but it was not saved.")
            self.bridge.busy.emit(False)
            return
        resolver.remember_server(name, ip, int(port))
        self.refresh()
        self.server_box.setCurrentText(name)
        self.bridge.status.emit(f"Saved {name} ({endpoint}).")
        self.bridge.busy.emit(False)

    def calibrate(self):
        self.calibration_dialog = CalibrationDialog(self)
        self.calibration_dialog.show()


STYLE = f"""
QMainWindow, QDialog {{ background: {BG}; color: {TEXT}; }}
QWidget {{ color: {TEXT}; font-family: 'Segoe UI'; font-size: 14px; }}
QFrame#sidebar {{ background: #10161d; border-right: 1px solid {LINE}; }}
QWidget#page {{ background: {BG}; }}
QFrame#card {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px; }}
QLabel[role='title'] {{ color: {TEXT}; font-size: 31px; font-weight: 650; }}
QLabel[role='pageTitle'] {{ color: {TEXT}; font-size: 35px; font-weight: 650; }}
QLabel[role='section'] {{ color: {TEXT}; font-size: 20px; font-weight: 600; }}
QLabel[role='body'], QLabel[role='lede'] {{ color: {MUTED}; }}
QLabel[role='lede'] {{ font-size: 16px; max-width: 700px; }}
QLabel[role='eyebrow'], QLabel[role='fieldLabel'], QLabel[role='number'] {{ color: {CYAN}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel[role='fieldLabel'] {{ color: {SUBTLE}; margin-top: 8px; }}
QLabel[role='helper'], QLabel[role='sideNote'] {{ color: {SUBTLE}; font-size: 12px; }}
QLabel[role='brand'] {{ color: {TEXT}; font-size: 15px; font-weight: 700; }}
QLabel[role='brandSub'] {{ color: {MUTED}; font-size: 10px; letter-spacing: 1px; }}
QLabel[role='number'] {{ font-size: 13px; }}
QLabel[role='warning'] {{ color: {AMBER}; font-weight: 600; }}
QLabel[role='status'] {{ color: {TEXT}; font-size: 15px; }}
QLabel[role='pill'] {{ color: {CYAN}; border: 1px solid #315a69; border-radius: 12px; padding: 4px 10px; font-size: 11px; font-weight: 700; }}
QLabel#brandMark {{ color: {CYAN}; border: 1px solid {CYAN}; border-radius: 5px; font-size: 21px; font-weight: 700; min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; }}
QFrame#rule {{ color: {LINE}; max-height: 1px; }}
QPushButton {{ background: {CARD}; color: {TEXT}; border: 1px solid #435364; border-radius: 6px; padding: 11px 16px; }}
QPushButton:hover {{ background: {CARD_HOVER}; border-color: {CYAN}; }}
QPushButton:pressed {{ background: #26394b; }}
QPushButton:disabled {{ color: {SUBTLE}; border-color: {LINE}; }}
QPushButton[kind='primary'] {{ background: {CYAN}; color: #071117; border-color: {CYAN}; font-weight: 700; }}
QPushButton[kind='primary']:hover {{ background: #9aebfa; }}
QPushButton[kind='nav'] {{ background: transparent; color: {MUTED}; border: 0; text-align: left; padding: 12px 10px; }}
QPushButton[kind='nav']:hover, QPushButton[kind='nav'][active='true'] {{ background: {CARD}; color: {TEXT}; }}
QLineEdit, QComboBox, QTextEdit {{ background: #0e151c; color: {TEXT}; border: 1px solid #425363; border-radius: 6px; padding: 10px 12px; selection-background-color: #27677a; }}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border-color: {CYAN}; }}
QComboBox::drop-down {{ border: 0; width: 30px; }}
QProgressBar {{ background: #0a121a; border: 0; border-radius: 3px; height: 6px; }}
QProgressBar::chunk {{ background: {CYAN}; border-radius: 3px; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #344756; border-radius: 6px; min-height: 35px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


def main():
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow(); window.show()
    app.exec()


if __name__ == "__main__":
    main()
