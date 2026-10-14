"""Advanced compact robot. Same clicked / set_state / has_alert API."""

import math

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient,
)
from PySide6.QtWidgets import QWidget


class BotMascot(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = "idle"
        self._phase = 0.0
        self.has_alert = False
        self.setMinimumSize(230, 280)
        self.setMaximumHeight(320)
        self.setCursor(Qt.PointingHandCursor)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(28)

    def set_state(self, state):
        self.state = state or "idle"
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _tick(self):
        speed = 0.08
        if self.state == "listening":
            speed = 0.16
        elif self.state == "speaking":
            speed = 0.2
        elif self.state == "thinking":
            speed = 0.11
        self._phase = (self._phase + speed) % 6.2832
        self.update()

    def _shell(self, painter, rect, radius):
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0, QColor("#FFFFFF"))
        grad.setColorAt(0.35, QColor("#E7F6FF"))
        grad.setColorAt(1, QColor("#8AA4BC"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor("#6E8CA6"), 1.2))
        painter.drawRoundedRect(rect, radius, radius)
        shine = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        shine.setColorAt(0, QColor(255, 255, 255, 180))
        shine.setColorAt(0.25, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(shine))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect.adjusted(6, 3, -10, -rect.height() * 0.62), radius, radius)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx = w / 2
        bob = 5 * math.sin(self._phase)
        if self.state == "speaking":
            bob = 7 * math.sin(self._phase * 1.6)
        if self.state == "listening":
            bob = 3 * math.sin(self._phase * 2)
        cy = h * 0.36 + bob

        glow_alpha = 70 + int(40 * abs(math.sin(self._phase)))
        if self.state == "listening":
            glow_alpha = 120
        glow = QRadialGradient(QPointF(cx, cy + 8), 125)
        glow.setColorAt(0, QColor(34, 211, 238, glow_alpha))
        glow.setColorAt(1, QColor(34, 211, 238, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(cx - 115, cy - 95, 230, 200))

        # orbit sparks
        for i in range(4):
            ang = self._phase * (1.4 if self.state != "thinking" else -1.8) + i * 1.57
            radius = 78 + (6 if self.state == "listening" else 0)
            sx = cx + math.cos(ang) * radius
            sy = cy + math.sin(ang) * 28
            p.setBrush(QColor(103, 232, 249, 180))
            p.drawEllipse(QRectF(sx - 2.5, sy - 2.5, 5, 5))

        p.setPen(QPen(QColor("#C5D2E2"), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(int(cx), int(cy - 78), int(cx), int(cy - 100))
        tip = QRadialGradient(QPointF(cx, cy - 106), 9)
        tip.setColorAt(0, QColor("#FFFFFF"))
        tip.setColorAt(1, QColor("#22D3EE"))
        p.setBrush(QBrush(tip))
        p.setPen(Qt.NoPen)
        pulse = 5 + (3 if self.state == "listening" else 1) * abs(math.sin(self._phase * 3))
        p.drawEllipse(QRectF(cx - pulse, cy - 106 - pulse, pulse * 2, pulse * 2))

        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(cx - 40, cy + 132, 80, 12))

        self._shell(p, QRectF(cx - 66, cy - 74, 132, 112), 52)

        visor = QRectF(cx - 52, cy - 48, 104, 60)
        vg = QLinearGradient(visor.topLeft(), visor.bottomLeft())
        vg.setColorAt(0, QColor("#1B3A52"))
        vg.setColorAt(1, QColor("#05080D"))
        p.setBrush(QBrush(vg))
        p.setPen(QPen(QColor("#67E8F9"), 1.3))
        p.drawRoundedRect(visor, 28, 28)

        scan = visor.top() + 8 + (visor.height() - 16) * (0.5 + 0.5 * math.sin(self._phase * 2.4))
        p.setPen(QPen(QColor(103, 232, 249, 110), 2))
        p.drawLine(int(visor.left() + 12), int(scan), int(visor.right() - 12), int(scan))

        blink = self.state == "idle" and abs(math.sin(self._phase * 0.55)) > 0.978
        eye_h = 4 if blink else 18
        look = 5 * math.sin(self._phase * 1.3) if self.state == "listening" else 2 * math.sin(self._phase * 0.4)
        eye = QColor("#67E8F9")
        if self.state == "thinking":
            eye = QColor("#FDE68A")
        if self.state == "error":
            eye = QColor("#FB7185")
        if self.state == "speaking":
            eye_h = 15
        for ex in (cx - 34 + look, cx + 12 + look):
            eg = QRadialGradient(QPointF(ex + 8, cy - 16), 14)
            eg.setColorAt(0, QColor("#FFFFFF"))
            eg.setColorAt(0.45, eye)
            eg.setColorAt(1, QColor("#0E7490"))
            p.setBrush(QBrush(eg))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(ex, cy - 22, 20, eye_h), 8, 8)

        if self.state == "speaking":
            mouth = 5 + 8 * abs(math.sin(self._phase * 5))
            p.setBrush(QColor("#22D3EE"))
            p.drawRoundedRect(QRectF(cx - 9, cy + 4, 18, mouth), 5, 5)
        elif self.state == "listening":
            p.setPen(QPen(QColor(103, 232, 249, 160), 2))
            p.setBrush(Qt.NoBrush)
            ring = 10 + 8 * abs(math.sin(self._phase * 3))
            p.drawEllipse(QRectF(cx - ring, cy - 6 - ring / 2, ring * 2, ring))
        else:
            p.setPen(QPen(QColor("#67E8F9"), 2, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(int(cx - 10), int(cy + 2), 20, 10, 200 * 16, 140 * 16)

        self._shell(p, QRectF(cx - 82, cy - 28, 16, 36), 7)
        self._shell(p, QRectF(cx + 66, cy - 28, 16, 36), 7)
        self._shell(p, QRectF(cx - 44, cy + 48, 88, 68), 28)

        p.setBrush(QColor("#0B1220"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(cx - 11, cy + 70, 22, 22))
        core = QRadialGradient(QPointF(cx, cy + 81), 10)
        core.setColorAt(0, QColor("#FFFFFF"))
        core.setColorAt(1, QColor("#FB7185" if self.state == "error" else "#22D3EE"))
        p.setBrush(QBrush(core))
        beat = 6 + (3 if self.state == "speaking" else 1) * abs(math.sin(self._phase * 3))
        p.drawEllipse(QRectF(cx - beat / 2, cy + 81 - beat / 2, beat, beat))

        p.setPen(QPen(QColor("#D7E1EC"), 8, Qt.SolidLine, Qt.RoundCap))
        sway = 10 * math.sin(self._phase if self.state != "speaking" else self._phase * 2)
        p.drawLine(int(cx - 42), int(cy + 70), int(cx - 74), int(cy + 108 + sway))
        p.drawLine(int(cx + 42), int(cy + 70), int(cx + 74), int(cy + 108 - sway))
        self._shell(p, QRectF(cx - 34, cy + 118, 22, 16), 6)
        self._shell(p, QRectF(cx + 12, cy + 118, 22, 16), 6)

        if self.has_alert:
            p.setBrush(QColor("#22D3EE"))
            p.setPen(QPen(QColor("#FFFFFF"), 2))
            p.drawEllipse(QRectF(cx + 48, cy - 82, 14, 14))
        p.end()