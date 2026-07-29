# SnapCap - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import config as cfg


class SettingsDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("SnapCap Settings")
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)
        self.config = config or cfg.load()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._save_tab(), "Save")
        tabs.addTab(self._capture_tab(), "Capture")
        tabs.addTab(self._shortcuts_tab(), "Shortcuts")
        tabs.addTab(self._preview_tab(), "Preview")

        layout.addWidget(tabs)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _general_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.chk_auto_copy = QCheckBox("Auto-copy to clipboard after capture")
        self.chk_auto_copy.setChecked(self.config["general.auto_copy"])
        layout.addWidget(self.chk_auto_copy)
        self.chk_auto_save = QCheckBox("Auto-save to folder")
        self.chk_auto_save.setChecked(self.config["general.auto_save"])
        layout.addWidget(self.chk_auto_save)
        self.chk_notification = QCheckBox("Show desktop notification")
        self.chk_notification.setChecked(self.config["general.notification"])
        layout.addWidget(self.chk_notification)

        self.chk_autostart = QCheckBox("Start daemon on login (autostart)")
        self.chk_autostart.setChecked(cfg.autostart_enabled())
        layout.addWidget(self.chk_autostart)

        layout.addStretch()
        return w

    def _save_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        path_row = QHBoxLayout()
        self.save_path = QLineEdit(self.config["save.directory"])
        path_row.addWidget(self.save_path)
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self._browse)
        path_row.addWidget(btn_browse)
        layout.addRow("Directory:", path_row)

        self.filename_fmt = QLineEdit(self.config["save.filename_format"])
        layout.addRow("Filename format:", self.filename_fmt)
        layout.addRow("", QLabel("Variables: %Y %m %d %H %M %S"))

        self.img_format = QComboBox()
        self.img_format.addItems(["PNG", "JPEG", "BMP", "WEBP"])
        self.img_format.setCurrentText(self.config["save.format"])
        layout.addRow("Image format:", self.img_format)

        self.quality = QSpinBox()
        self.quality.setRange(-1, 100)
        self.quality.setValue(self.config["save.quality"])
        self.quality.setSpecialValueText("Default")
        layout.addRow("Quality:", self.quality)

        return w

    def _capture_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.capture_mode = QComboBox()
        self.capture_mode.addItems(["region", "fullscreen"])
        self.capture_mode.setCurrentText(self.config["capture.mode"])
        layout.addRow("Mode:", self.capture_mode)

        self.delay = QSpinBox()
        self.delay.setRange(0, 60)
        self.delay.setSuffix(" sec")
        self.delay.setValue(self.config["capture.delay"])
        layout.addRow("Delay:", self.delay)

        self.include_cursor = QCheckBox()
        self.include_cursor.setChecked(self.config["capture.include_cursor"])
        layout.addRow("Include cursor:", self.include_cursor)

        self.copy_tool = QComboBox()
        self.copy_tool.addItems(["wl-copy", "qt", "both"])
        self.copy_tool.setCurrentText(self.config["clipboard.tool"])
        layout.addRow("Clipboard tool:", self.copy_tool)

        return w

    def _shortcuts_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.sc_save = QLineEdit(self.config["shortcuts.save"])
        layout.addRow("Save:", self.sc_save)
        self.sc_copy = QLineEdit(self.config["shortcuts.copy"])
        layout.addRow("Copy:", self.sc_copy)
        self.sc_new = QLineEdit(self.config["shortcuts.new_capture"])
        layout.addRow("New Capture:", self.sc_new)
        self.sc_close = QLineEdit(self.config["shortcuts.close"])
        layout.addRow("Close:", self.sc_close)

        layout.addRow("", QLabel("Format: Ctrl+S, Ctrl+Shift+A, Escape, etc."))

        return w

    def _preview_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.max_width = QSpinBox()
        self.max_width.setRange(200, 4000)
        self.max_width.setValue(self.config["preview.max_width"])
        layout.addRow("Max thumbnail size:", self.max_width)

        self.win_w = QSpinBox()
        self.win_w.setRange(200, 2000)
        self.win_w.setValue(self.config["preview.window_width"])
        layout.addRow("Window width:", self.win_w)

        self.win_h = QSpinBox()
        self.win_h.setRange(200, 2000)
        self.win_h.setValue(self.config["preview.window_height"])
        layout.addRow("Window height:", self.win_h)

        self.stay_on_top = QCheckBox()
        self.stay_on_top.setChecked(self.config["preview.stay_on_top"])
        layout.addRow("Stay on top:", self.stay_on_top)

        return w

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select save directory")
        if path:
            self.save_path.setText(path)

    def _save(self):
        self.config["general.auto_copy"] = self.chk_auto_copy.isChecked()
        self.config["general.auto_save"] = self.chk_auto_save.isChecked()
        self.config["general.notification"] = self.chk_notification.isChecked()
        self.config["save.directory"] = self.save_path.text()
        self.config["save.filename_format"] = self.filename_fmt.text()
        self.config["save.format"] = self.img_format.currentText()
        self.config["save.quality"] = self.quality.value()
        self.config["capture.mode"] = self.capture_mode.currentText()
        self.config["capture.delay"] = self.delay.value()
        self.config["capture.include_cursor"] = self.include_cursor.isChecked()
        self.config["clipboard.tool"] = self.copy_tool.currentText()
        self.config["shortcuts.save"] = self.sc_save.text()
        self.config["shortcuts.copy"] = self.sc_copy.text()
        self.config["shortcuts.new_capture"] = self.sc_new.text()
        self.config["shortcuts.close"] = self.sc_close.text()
        self.config["preview.max_width"] = self.max_width.value()
        self.config["preview.window_width"] = self.win_w.value()
        self.config["preview.window_height"] = self.win_h.value()
        self.config["preview.stay_on_top"] = self.stay_on_top.isChecked()
        if self.chk_autostart.isChecked():
            cfg.install_autostart()
        else:
            cfg.remove_autostart()
        cfg.save(self.config)
        self.accept()
