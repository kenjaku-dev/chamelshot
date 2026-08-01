from __future__ import annotations

import math
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

TOOLS = ["pen", "highlighter", "arrow", "rect", "circle", "line", "text", "numbering", "blur"]


@dataclass
class Annotation:
    tool: str
    points: list = field(default_factory=list)
    color: QColor = field(default_factory=lambda: QColor(255, 50, 50))
    width: float = 3.0
    text: str = ""
    blur_radius: int = 10
    font_size: int = 16
    number: int = 0


class AnnotationCanvas(QWidget):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._source: QPixmap | None = None
        self._src_image: QImage | None = None
        self.source = pixmap
        self.annotations: list[Annotation] = []
        self.current: Annotation | None = None
        self.tool = "pen"
        self.color = QColor(255, 50, 50)
        self.pen_width = 3.0
        self.blur_radius = 10
        self.font_size = 16
        self.numbering_counter: int = 0
        self._history: list[list[Annotation]] = []
        self._redo_stack: list[list[Annotation]] = []

        self.setMouseTracking(True)
        self.setMinimumSize(200, 150)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._update_cursor()

    @property
    def source(self) -> QPixmap:
        if self._source is None:
            raise RuntimeError("source pixmap not set")  # noqa: TRY003 - internal invariant
        return self._source

    @source.setter
    def source(self, pixmap: QPixmap):
        self._source = pixmap
        self._src_image = None

    def _source_image(self) -> QImage:
        if self._src_image is None:
            self._src_image = self.source.toImage()
        return self._src_image

    def _draw_at(self) -> QRectF:
        pw, ph = self.source.width(), self.source.height()
        cw, ch = self.width(), self.height()
        scale = min(cw / pw, ch / ph, 1.0)
        dw, dh = pw * scale, ph * scale
        x = (cw - dw) / 2
        y = (ch - dh) / 2
        return QRectF(x, y, dw, dh)

    def _map_to_source(self, pos: QPointF) -> QPointF:
        r = self._draw_at()
        if r.width() == 0 or r.height() == 0:
            return QPointF(0, 0)
        return QPointF(
            (pos.x() - r.x()) * self.source.width() / r.width(),
            (pos.y() - r.y()) * self.source.height() / r.height(),
        )

    def _update_cursor(self):
        cursors = {
            "pen": Qt.CursorShape.CrossCursor,
            "highlighter": Qt.CursorShape.CrossCursor,
            "arrow": Qt.CursorShape.CrossCursor,
            "rect": Qt.CursorShape.CrossCursor,
            "circle": Qt.CursorShape.CrossCursor,
            "line": Qt.CursorShape.CrossCursor,
            "text": Qt.CursorShape.IBeamCursor,
            "numbering": Qt.CursorShape.CrossCursor,
            "blur": Qt.CursorShape.CrossCursor,
        }
        self.setCursor(cursors.get(self.tool, Qt.CursorShape.ArrowCursor))

    def _save_state(self):
        import copy

        self._history.append(copy.deepcopy(self.annotations))
        self._redo_stack.clear()

    def undo(self):
        if not self._history:
            return
        import copy

        self._redo_stack.append(copy.deepcopy(self.annotations))
        self.annotations = self._history.pop()
        self.update()

    def redo(self):
        if not self._redo_stack:
            return
        import copy

        self._history.append(copy.deepcopy(self.annotations))
        self.annotations = self._redo_stack.pop()
        self.update()

    def clear_all(self):
        if self.annotations:
            self._save_state()
        self.annotations.clear()
        self.update()

    def result_pixmap(self) -> QPixmap:
        result = QPixmap(self.source.size())
        result.fill(Qt.GlobalColor.transparent)
        p = QPainter(result)
        p.drawPixmap(0, 0, self.source)
        self._paint_annotations(p, result.size(), 1.0)
        p.end()
        return result

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape and self.current is not None:
            self.current = None
            self.update()
        elif event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z and not event.isAutoRepeat():
                self.undo()
            elif event.key() == Qt.Key.Key_Y and not event.isAutoRepeat():
                self.redo()
        super().keyPressEvent(event)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._draw_at()
        p.drawPixmap(r, self.source, QRectF(self.source.rect()))
        p.save()
        p.translate(r.x(), r.y())
        scale = r.width() / self.source.width() if self.source.width() else 1
        self._paint_annotations(p, self.size(), scale)
        p.restore()
        p.end()

    def _paint_annotations(self, p: QPainter, canvas_size, scale: float):
        all_items = list(self.annotations)
        if self.current:
            all_items.append(self.current)

        for ann in all_items:
            p.save()
            if scale != 1.0:
                p.scale(scale, scale)
            pen = QPen(ann.color, max(1, ann.width * (1 / scale)))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

            if ann.tool == "blur":
                self._paint_blur(p, ann, canvas_size, scale)
            elif ann.tool in ("pen", "highlighter"):
                if len(ann.points) > 1:
                    path = QPainterPath()
                    path.moveTo(ann.points[0])
                    for pt in ann.points[1:]:
                        path.lineTo(pt)
                    if ann.tool == "highlighter":
                        c = QColor(ann.color)
                        c.setAlpha(80)
                        hl_pen = QPen(c, max(1, ann.width * 5 * (1 / scale)))
                        hl_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        hl_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                        p.strokePath(path, hl_pen)
                    else:
                        p.strokePath(path, pen)
            elif ann.tool == "arrow" and len(ann.points) >= 2:
                self._paint_arrow(p, ann, pen)
            elif ann.tool in ("rect", "circle") and len(ann.points) >= 2:
                rect = QRectF(ann.points[0], ann.points[1])
                p.setPen(pen)
                if ann.tool == "rect":
                    p.drawRect(rect)
                else:
                    p.drawEllipse(rect)
            elif ann.tool == "line" and len(ann.points) >= 2:
                p.setPen(pen)
                p.drawLine(ann.points[0], ann.points[1])
            elif ann.tool == "text" and ann.points:
                font = QFont()
                font.setPixelSize(int(ann.font_size * (1 / scale)))
                p.setFont(font)
                p.setPen(pen)
                p.drawText(ann.points[0], ann.text)
            elif ann.tool == "numbering" and ann.points:
                pt = ann.points[0]
                r = max(12, int(ann.font_size * 0.6 * (1 / scale)))
                p.setPen(QPen(ann.color, max(2, ann.width * (1 / scale))))
                p.setBrush(Qt.GlobalColor.white)
                p.drawEllipse(pt, r, r)
                font = QFont()
                font.setPixelSize(int(ann.font_size * (1 / scale)))
                p.setFont(font)
                p.setPen(QPen(ann.color, 1))
                p.drawText(QRectF(pt.x() - r, pt.y() - r, r * 2, r * 2), Qt.AlignmentFlag.AlignCenter, str(ann.number))
            p.restore()

    def _paint_blur(self, p: QPainter, ann: Annotation, canvas_size, scale: float):
        if len(ann.points) < 2:
            return
        rect = QRectF(ann.points[0], ann.points[1])
        if rect.isEmpty():
            return
        src = self._source_image()
        region = src.copy(rect.toRect())
        blurred = _box_blur(region, max(1, ann.blur_radius))
        p.drawImage(rect.topLeft(), blurred)

    def _paint_arrow(self, p: QPainter, ann: Annotation, pen: QPen):
        a, b = ann.points[0], ann.points[-1]
        p.setPen(pen)
        p.drawLine(a, b)
        angle = math.atan2(b.y() - a.y(), b.x() - a.x())
        head_len = max(10, ann.width * 5)
        pts = [b]
        for sign in (-1, 1):
            x = b.x() - head_len * math.cos(angle + sign * 0.45)
            y = b.y() - head_len * math.sin(angle + sign * 0.45)
            pts.append(QPointF(x, y))
        path = QPainterPath()
        path.moveTo(pts[0])
        path.lineTo(pts[1])
        path.lineTo(pts[2])
        path.closeSubpath()
        p.fillPath(path, pen.color())
        p.strokePath(path, pen)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._save_state()
        pos = self._map_to_source(event.position())
        ann = Annotation(tool=self.tool, color=QColor(self.color), width=self.pen_width)
        if self.tool == "text":
            text, ok = QInputDialog.getText(self, "Text", "Enter text:")
            if ok and text:
                ann.points.append(pos)
                ann.text = text
                ann.font_size = self.font_size
                self.annotations.append(ann)
                self.update()
            return
        if self.tool == "numbering":
            self.numbering_counter += 1
            ann.points.append(pos)
            ann.number = self.numbering_counter
            ann.font_size = self.font_size
            self.annotations.append(ann)
            self.update()
            return
        if self.tool == "blur":
            ann.blur_radius = self.blur_radius
        ann.points.append(pos)
        self.current = ann

    def mouseMoveEvent(self, event):  # noqa: N802
        if self.current is None:
            return
        pos = self._map_to_source(event.position())
        if self.tool == "pen":
            pts = self.current.points
            if not pts or (pos - pts[-1]).manhattanLength() >= 2.0:
                self.current.points.append(pos)
        else:
            if len(self.current.points) >= 2:
                self.current.points[-1] = pos
            else:
                self.current.points.append(pos)
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if self.current is None or event.button() != Qt.MouseButton.LeftButton:
            return
        if self.tool != "pen" and len(self.current.points) > 1:
            self.current.points[-1] = self._map_to_source(event.position())
        if self.current.points:
            self.annotations.append(self.current)
            if self.current.tool == "pen" and len(self.current.points) < 2:
                self.annotations.pop()
        self.current = None
        self.update()


def _box_blur(src: QImage, radius: int) -> QImage:
    """Native box-blur approximation.

    Downscaling with SmoothTransformation averages each (s x s) block, then
    scaling back up interpolates — a box blur of extent ~s. The old pure-Python
    per-pixel sliding window took ~10s on 1280x720; this runs in a few ms and
    never touches pixels from Python.
    """
    if radius < 1 or src.isNull() or src.width() < 2 or src.height() < 2:
        return src
    w, h = src.width(), src.height()
    s = min(2 * radius + 1, max(w, h))
    if s <= 1:
        return src
    small = src.scaled(
        max(1, w // s),
        max(1, h // s),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return small.scaled(
        w,
        h,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


TOOL_GLYPH = {
    "pen": "Pen",
    "highlighter": "HL",
    "arrow": "Arr",
    "rect": "Rect",
    "circle": "Oval",
    "line": "Line",
    "text": "T",
    "numbering": "No.",
    "blur": "Blur",
}


class Annotator(QWidget):
    accepted = Signal(QPixmap)
    cancelled = Signal()

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.canvas = AnnotationCanvas(pixmap)
        self._build_toolbar()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.toolbar)

    def _build_toolbar(self):
        self.toolbar = QFrame()
        self.toolbar.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self.toolbar)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        tool_row = QHBoxLayout()
        tool_row.setSpacing(2)
        self.tool_btns = {}
        for name in TOOLS:
            btn = QPushButton(TOOL_GLYPH.get(name, name[0].upper()))
            btn.setCheckable(True)
            btn.setToolTip(name.capitalize())
            btn.setFixedSize(32, 32)
            btn.clicked.connect(lambda _, t=name: self._select_tool(t))
            self.tool_btns[name] = btn
            tool_row.addWidget(btn)
        self.tool_btns["pen"].setChecked(True)

        tool_row.addStretch()

        self.btn_undo = QPushButton("↩")
        self.btn_undo.setFixedSize(32, 32)
        self.btn_undo.setToolTip("Undo")
        self.btn_undo.clicked.connect(self.canvas.undo)
        tool_row.addWidget(self.btn_undo)

        self.btn_redo = QPushButton("↪")
        self.btn_redo.setFixedSize(32, 32)
        self.btn_redo.setToolTip("Redo")
        self.btn_redo.clicked.connect(self.canvas.redo)
        tool_row.addWidget(self.btn_redo)

        self.btn_clear = QPushButton("✕")
        self.btn_clear.setFixedSize(32, 32)
        self.btn_clear.setToolTip("Clear all")
        self.btn_clear.clicked.connect(self.canvas.clear_all)
        tool_row.addWidget(self.btn_clear)

        layout.addLayout(tool_row)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(QLabel("Color:"))
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(28, 28)
        self._update_color_btn(self.canvas.color)
        self.color_btn.clicked.connect(self._pick_color)
        controls.addWidget(self.color_btn)

        controls.addWidget(QLabel("Width:"))
        self.pen_width_spin = QSpinBox()
        self.pen_width_spin.setRange(1, 50)
        self.pen_width_spin.setValue(int(self.canvas.pen_width))
        self.pen_width_spin.valueChanged.connect(lambda v: setattr(self.canvas, "pen_width", v))
        controls.addWidget(self.pen_width_spin)

        controls.addWidget(QLabel("Font:"))
        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 120)
        self.font_spin.setValue(self.canvas.font_size)
        self.font_spin.valueChanged.connect(lambda v: setattr(self.canvas, "font_size", v))
        controls.addWidget(self.font_spin)

        self.blur_label = QLabel("Blur:")
        controls.addWidget(self.blur_label)
        self.blur_spin = QSpinBox()
        self.blur_spin.setRange(2, 50)
        self.blur_spin.setValue(self.canvas.blur_radius)
        self.blur_spin.valueChanged.connect(lambda v: setattr(self.canvas, "blur_radius", v))
        self.blur_spin.setEnabled(False)
        self.blur_label.setVisible(False)
        controls.addWidget(self.blur_spin)

        controls.addStretch()

        self.btn_apply = QPushButton("✓ Apply")
        self.btn_apply.clicked.connect(self._apply)
        controls.addWidget(self.btn_apply)

        self.btn_cancel = QPushButton("✗ Cancel")
        self.btn_cancel.clicked.connect(lambda: self.cancelled.emit())
        controls.addWidget(self.btn_cancel)

        layout.addLayout(controls)

    def _select_tool(self, name: str):
        self.canvas.tool = name
        self.canvas._update_cursor()
        for n, btn in self.tool_btns.items():
            btn.setChecked(n == name)
        self.blur_spin.setEnabled(name == "blur")
        self.blur_label.setVisible(name == "blur")

    def _update_color_btn(self, color: QColor):
        self.color_btn.setStyleSheet(f"background-color: {color.name()}; border: 1px solid gray;")

    def _pick_color(self):
        c = QColorDialog.getColor(self.canvas.color, self, "Pick Color")
        if c.isValid():
            self.canvas.color = c
            self._update_color_btn(c)

    def _apply(self):
        self.accepted.emit(self.canvas.result_pixmap())
