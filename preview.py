# ChamelShot - Screenshot capture tool for Wayland
# Copyright (C) 2026  Ashraf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import datetime
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import clipboard as clip
import config as cfg
import proc
import theme as t
from dispatcher import run_async
from editor import Annotator


def _history_add(saved_path):
    """Copy an already-saved file into the history (no second PNG encode)."""
    hist_dir = cfg.HISTORY_DIR
    hist_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = hist_dir / f"screenshot_{ts}.png"
    shutil.copy2(saved_path, dest)
    entries = sorted(hist_dir.glob("screenshot_*.png"), reverse=True)
    for old in entries[cfg.MAX_HISTORY :]:
        old.unlink(missing_ok=True)


def _notify_args(message: str, image: str | None = None, preview: bool = True) -> list[str]:
    """Build the notify-send argv; `-i <image>` shows a thumbnail when preview is on."""
    args = ["notify-send"]
    if preview and image:
        args.extend(["-i", image])
    args.extend(["ChamelShot", message])
    return args


class ExportDialog(QDialog):
    def __init__(self, pixmap: QPixmap, config: dict, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.cfg = config
        self.setWindowTitle("Export Screenshot")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["PNG", "JPEG", "WebP", "BMP"])
        self.fmt_combo.setCurrentText(self.cfg.get("save.format", "PNG"))
        self.fmt_combo.currentTextChanged.connect(self._on_format_changed)
        form.addRow("Format:", self.fmt_combo)

        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(self.cfg.get("save.quality", 85) if self.cfg.get("save.quality", -1) > 0 else 85)
        self.quality_label = QLabel(str(self.quality_slider.value()))
        self.quality_slider.valueChanged.connect(lambda v: self.quality_label.setText(str(v)))
        qh = QHBoxLayout()
        qh.addWidget(self.quality_slider, 1)
        qh.addWidget(self.quality_label)
        self.quality_row = QWidget()
        self.quality_row.setLayout(qh)
        form.addRow("Quality:", self.quality_row)
        self._on_format_changed(self.fmt_combo.currentText())

        self.path_input = QPushButton("Choose save location...")
        self.path_input.clicked.connect(self._choose_path)
        self._save_path = ""
        form.addRow("Save to:", self.path_input)

        layout.addLayout(form)
        layout.addStretch()

        btn_box = QDialogButtonBox(self)
        btn_box.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_copy = btn_box.addButton("Copy", QDialogButtonBox.ButtonRole.ActionRole)
        btn_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        btn_copy.clicked.connect(self._copy_and_close)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_format_changed(self, fmt: str):
        enabled = fmt in ("JPEG", "WebP")
        self.quality_row.setVisible(enabled)

    def _choose_path(self):
        fmt = self.fmt_combo.currentText()
        default_dir = self.cfg.get("save.directory", str(Path.home()))
        default_path = os.path.join(default_dir, f"chamelshot.{fmt.lower()}")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Screenshot",
            default_path,
            f"{fmt} (*.{fmt.lower()})",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self._save_path = path
            self.path_input.setText(os.path.basename(path))

    def _copy_and_close(self):
        self._do_copy()
        self.accept()

    def _do_copy(self):
        clip.copy_pixmap(self.pixmap, self.cfg)

    def export(self) -> tuple[str, str, int] | None:
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        fmt = self.fmt_combo.currentText()
        quality = self.quality_slider.value() if fmt in ("JPEG", "WebP") else -1
        path = self._save_path
        return (path, fmt, quality)


ACTION_STYLE = f"""
    QPushButton {{
        background: {t.CHROME_BTN_BG};
        color: {t.TEXT_WHITE};
        border: 1px solid {t.CHROME_BTN_BORDER};
        border-radius: {t.RADIUS_SMALL};
        padding: 6px 14px;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background: {t.CHROME_BTN_HOVER};
        border-color: {t.CHROME_BTN_BORDER_HOVER};
    }}
    QPushButton:pressed {{
        background: {t.CHROME_BTN_PRESSED};
    }}
"""


class PreviewWindow(QWidget):
    def __init__(
        self,
        pixmap: QPixmap,
        config: dict | None = None,
        on_new_capture=None,
        source_path: str | None = None,
        pin_store=None,
        on_pin=None,
        on_edit_pin=None,
    ):
        super().__init__()
        self.pixmap = pixmap
        self.cfg = config or cfg.load()
        self.on_new_capture = on_new_capture
        self.source_path = source_path  # re-emit session: save()/quick-save target this file
        self.on_pin = on_pin  # called with _current_pixmap(); None uses internal store
        self.pin_store = pin_store  # PinStore used when on_pin is None (unit+tests)
        self.on_edit_pin = on_edit_pin  # opened by the pin's "Re-edit" action
        self.setWindowTitle("ChamelShot - Screenshot")

        if self.cfg.get("preview.stay_on_top", True):
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        win_w = self.cfg.get("preview.window_width", 600)
        win_h = self.cfg.get("preview.window_height", 450)
        self.setMinimumSize(400, 300)
        self.resize(win_w, win_h)

        layout = QVBoxLayout(self)

        max_w = self.cfg.get("preview.max_width", 800)
        w, h = pixmap.width(), pixmap.height()
        display = pixmap
        if w > max_w or h > max_w:
            display = pixmap.scaled(
                max_w,
                max_w,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        self.stack = QStackedWidget()

        self.preview_container = QWidget()
        pc_layout = QVBoxLayout(self.preview_container)
        pc_layout.setContentsMargins(0, 0, 0, 0)
        pc_layout.setSpacing(0)

        self.preview_label = QLabel()
        self.preview_label.setPixmap(display)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pc_layout.addWidget(self.preview_label, 1)

        self.action_overlay = QWidget()
        self.action_overlay.setStyleSheet(f"background: {t.CHROME_TILE_BG}; border-radius: {t.RADIUS};")
        ol_layout = QHBoxLayout(self.action_overlay)
        ol_layout.setContentsMargins(8, 6, 8, 6)
        ol_layout.setSpacing(6)

        self.btn_quick_save = QPushButton("Quick Save")
        self.btn_quick_save.setToolTip("Save to default directory")
        self.btn_quick_save.setStyleSheet(ACTION_STYLE)
        self.btn_quick_save.clicked.connect(self._quick_save)
        ol_layout.addWidget(self.btn_quick_save)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setToolTip("Copy to clipboard")
        self.btn_copy.setStyleSheet(ACTION_STYLE)
        self.btn_copy.clicked.connect(lambda: self.copy_to_clipboard())
        ol_layout.addWidget(self.btn_copy)

        self.btn_copy_primary = QPushButton("Copy Primary")
        self.btn_copy_primary.setToolTip("Copy to clipboard and primary selection (middle-click paste)")
        self.btn_copy_primary.setStyleSheet(ACTION_STYLE)
        self.btn_copy_primary.setEnabled(clip.wl_copy_supported(self.cfg))
        self.btn_copy_primary.clicked.connect(lambda: self.copy_to_clipboard(primary=True))
        ol_layout.addWidget(self.btn_copy_primary)

        self.btn_export = QPushButton("Export")
        self.btn_export.setToolTip("Export with format and quality options")
        self.btn_export.setStyleSheet(ACTION_STYLE)
        self.btn_export.clicked.connect(self._export_dialog)
        ol_layout.addWidget(self.btn_export)

        self.btn_open = QPushButton("Open")
        self.btn_open.setToolTip("Open in default image viewer")
        self.btn_open.setStyleSheet(ACTION_STYLE)
        self.btn_open.clicked.connect(self._open_viewer)
        ol_layout.addWidget(self.btn_open)

        self.btn_pin = QPushButton("Pin")
        self.btn_pin.setToolTip("Pin this image on screen as a reference")
        self.btn_pin.setStyleSheet(ACTION_STYLE)
        self.btn_pin.clicked.connect(self._pin)
        ol_layout.addWidget(self.btn_pin)

        pc_layout.addWidget(self.action_overlay)

        self.stack.addWidget(self.preview_container)
        self.annotator = Annotator(pixmap)
        self.annotator.accepted.connect(self._on_annotated)
        self.annotator.cancelled.connect(self._show_preview)
        self.stack.addWidget(self.annotator)
        self.stack.setCurrentWidget(self.preview_container)
        layout.addWidget(self.stack, 1)

        btn_frame = QWidget()
        btn_frame.setStyleSheet(
            f"QWidget {{ background: {t.CHROME_BG}; border-radius: {t.RADIUS_LARGE}; }}"
            f" QPushButton {{ background: transparent; color: {t.CHROME_TEXT}; border: 1px solid {t.CHROME_BORDER};"
            f" border-radius: {t.RADIUS_MID}; padding: 6px 14px; font-size: 12px; }}"
            f" QPushButton:hover {{ background: {t.CHROME_HOVER}; color: {t.TEXT_WHITE};"
            f" border-color: {t.CHROME_BORDER_HOVER}; }}"
            f" QPushButton:pressed {{ background: {t.CHROME_PRESSED}; }}"
        )
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(8, 6, 8, 6)
        btn_layout.setSpacing(6)
        btn_capture = QPushButton("New Capture")
        btn_capture.clicked.connect(self.new_capture)
        btn_layout.addWidget(btn_capture)
        btn_layout.addStretch()
        btn_annotate = QPushButton("Annotate")
        btn_annotate.clicked.connect(self._show_annotator)
        btn_layout.addWidget(btn_annotate)
        btn_settings = QPushButton("Settings")
        btn_settings.clicked.connect(self._open_settings)
        btn_layout.addWidget(btn_settings)
        btn_close = QPushButton("Close")
        btn_close.setToolTip("Minimize to tray")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)
        btn_kill = QPushButton("Kill")
        btn_kill.setToolTip("Exit ChamelShot")
        btn_kill.clicked.connect(QApplication.quit)
        btn_layout.addWidget(btn_kill)
        layout.addWidget(btn_frame)

        self._bind_shortcuts()
        self._apply_auto_actions()

    def _pin(self):
        from pin import PinStore, PinWindow

        pixmap = self._current_pixmap()
        if self.on_pin:
            self.on_pin(pixmap)
            return
        store = self.pin_store or PinStore()
        self.pin_store = store
        window = PinWindow(pixmap, store, on_reedit=self.on_edit_pin)
        window.show()

    def _bind_shortcuts(self):
        mapping = {
            "save": self.save,
            "copy": self.copy_to_clipboard,
            "copy_primary": lambda: self.copy_to_clipboard(primary=True),
            "close": self.close,
            "pin": self._pin,
        }
        if self.on_new_capture:
            mapping["new_capture"] = self.new_capture
        for key, fn in mapping.items():
            raw = self.cfg.get(f"shortcuts.{key}", "")
            if raw:
                ks = QKeySequence.fromString(raw)
                if not ks.isEmpty():
                    QShortcut(ks, self).activated.connect(fn)

    def _apply_auto_actions(self):
        if self.cfg.get("general.auto_save"):
            QTimer.singleShot(0, lambda: self._quick_save(close=False))
        if self.cfg.get("general.auto_copy"):
            QTimer.singleShot(50, lambda: self.copy_to_clipboard(closing=False))

    def _notify(self, message: str, image: str | None = None):
        if not self.cfg.get("general.notification", True):
            return
        try:
            subprocess.Popen(
                _notify_args(message, image, self.cfg.get("general.notification_preview", True)),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=proc.env(),
            )
        except Exception:
            pass

    def _open_settings(self):
        from settings import SettingsDialog

        dlg = SettingsDialog(self, config=self.cfg)
        if dlg.exec():
            self.cfg = cfg.load()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        screen = self.screen()
        if screen:
            center = screen.availableGeometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def _current_pixmap(self) -> QPixmap:
        if self.stack.currentWidget() == self.annotator and self.annotator.canvas.annotations:
            return self.annotator.canvas.result_pixmap()
        return self.pixmap

    def _current_image(self) -> QImage:
        return self._current_pixmap().toImage()

    def _async_error(self, title: str):
        def _err(e):
            QMessageBox.warning(self, title, str(e))

        return _err

    def _save_async(self, img: QImage, path: str, fmt: str, quality: int, close: bool = True):
        """Encode + write + history-copy in a worker thread; UI stays responsive."""
        if not isinstance(path, str) or not path:
            return

        source_path = getattr(self, "source_path", None)
        overwrite_source = source_path and os.path.abspath(path) == os.path.abspath(source_path)

        def work():
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # PySide6 stubs type the format parameter as bytes (const char*).
            fmt_bytes = fmt.encode()
            ok = img.save(path, fmt_bytes) if quality < 0 else img.save(path, fmt_bytes, quality)
            if not ok:
                raise RuntimeError(f"Failed to write file: {path}")
            if not overwrite_source:
                _history_add(path)
            return path

        def done(saved_path):
            self._notify(f"Saved to {saved_path}", image=str(saved_path))
            if close:
                self.close()

        run_async(self, work, done, self._async_error("Save Error"))

    def save(self):
        fmt = self.cfg.get("save.format", "PNG")
        source_path = getattr(self, "source_path", None)
        default_path = source_path or cfg.generate_save_path(self.cfg)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Screenshot",
            default_path,
            f"{fmt} (*.{fmt.lower()})",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            img = self._current_image()
            self._save_async(img, path, fmt, self.cfg.get("save.quality", -1))

    def copy_to_clipboard(self, closing=True, primary=False):
        try:
            img = self._current_image()
            tool = self.cfg.get("clipboard.tool", "wl-copy")
            use_wl = clip.wl_copy_supported(self.cfg)
            use_qt = tool in ("qt", "both")
            if primary and not use_wl:
                QMessageBox.warning(
                    self,
                    "Copy Primary",
                    "Primary selection requires the wl-copy clipboard tool.",
                )
                return

            def work():
                png_data = clip.image_png(img)
                if png_data is None:
                    raise RuntimeError("Failed to encode PNG")
                if use_wl:
                    targets = [False]
                    if primary:
                        targets.append(True)
                    for is_primary in targets:
                        clip.wl_copy(png_data, is_primary)
                return png_data

            def done(_png_data):
                if use_qt:
                    QApplication.clipboard().setPixmap(QPixmap.fromImage(img))
                self._notify("Copied to clipboard")
                if closing:
                    self.close()

            run_async(self, work, done, self._async_error("Copy Error"))
        except Exception as e:
            QMessageBox.warning(self, "Copy Error", str(e))

    def _show_annotator(self):
        self.annotator.canvas.source = self.pixmap
        self.annotator.canvas.annotations.clear()
        self.annotator.canvas._history.clear()
        self.annotator.canvas._redo_stack.clear()
        self.annotator.canvas.update()
        self.stack.setCurrentWidget(self.annotator)

    def _show_preview(self):
        self.stack.setCurrentWidget(self.preview_container)

    def _on_annotated(self, annotated: QPixmap):
        self.pixmap = annotated
        self._update_preview_display()
        self._show_preview()

    def _update_preview_display(self):
        max_w = self.cfg.get("preview.max_width", 800)
        w, h = self.pixmap.width(), self.pixmap.height()
        display = self.pixmap
        if w > max_w or h > max_w:
            display = self.pixmap.scaled(
                max_w,
                max_w,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.preview_label.setPixmap(display)

    def _quick_save(self, close=True):
        try:
            source_path = getattr(self, "source_path", None)
            path = source_path or cfg.generate_save_path(self.cfg)
            img = self._current_image()
            fmt = self.cfg.get("save.format", "PNG")
            self._save_async(img, path, fmt, self.cfg.get("save.quality", -1), close=close)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def _export_dialog(self):
        dlg = ExportDialog(self._current_pixmap(), self.cfg, self)
        result = dlg.export()
        if result is None:
            return
        path, fmt, quality = result
        if path:
            img = self._current_image()
            self._save_async(img, path, fmt, quality)

    def _open_viewer(self):
        img = self._current_image()
        fd, name = tempfile.mkstemp(prefix="chamelshot_preview_", suffix=".png")
        os.close(fd)
        path = Path(name)

        def work():
            try:
                if not img.save(str(path), b"PNG"):
                    raise RuntimeError("Failed to write preview file")
            except Exception:
                path.unlink(missing_ok=True)
                raise
            return path

        def done(tmp_path):
            for viewer in ("xdg-open", "gimp", "eog", "feh", "qiv", "sxiv"):
                if shutil.which(viewer):
                    subprocess.Popen(
                        [viewer, str(tmp_path)],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=proc.env(),
                    )
                    break
            # Concise: viewers may read the file lazily (feh/eog/sxiv return
            # before reading), so delete it shortly after spawn, not before.
            QTimer.singleShot(30_000, lambda: tmp_path.unlink(missing_ok=True))

        run_async(self, work, done, self._async_error("Open Error"))

    def new_capture(self):
        self.close()
        if self.on_new_capture:
            self.on_new_capture()
