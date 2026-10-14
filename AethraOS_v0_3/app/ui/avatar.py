import math

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QPainter,
    QPen,
    QColor,
    QBrush,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget


class AethraAvatar(QWidget):
    """
    Friendly holographic droid avatar for AethraOS.

    Supported states:
    - idle
    - listening
    - thinking
    - speaking
    - error
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.state = "idle"
        self.animation_value = 0.0

        self.setMinimumSize(220, 220)
        self.setMaximumHeight(280)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)

    # ---------------------------------------------------------
    # STATE
    # ---------------------------------------------------------

    def set_state(self, state):
        valid_states = {
            "idle",
            "listening",
            "thinking",
            "speaking",
            "error",
        }

        if state not in valid_states:
            state = "idle"

        self.state = state
        self.update()

    # ---------------------------------------------------------
    # ANIMATION
    # ---------------------------------------------------------

    def animate(self):
        speeds = {
            "idle": 0.035,
            "listening": 0.12,
            "thinking": 0.16,
            "speaking": 0.18,
            "error": 0.08,
        }

        self.animation_value += speeds.get(
            self.state,
            0.035
        )

        self.animation_value %= math.pi * 2
        self.update()

    # ---------------------------------------------------------
    # COLOURS
    # ---------------------------------------------------------

    def get_state_color(self):
        colors = {
            "idle": QColor("#36A3FF"),
            "listening": QColor("#00E5FF"),
            "thinking": QColor("#FFC857"),
            "speaking": QColor("#B56CFF"),
            "error": QColor("#FF4D6D"),
        }

        return colors.get(
            self.state,
            QColor("#36A3FF")
        )

    # ---------------------------------------------------------
    # DRAWING HELPERS
    # ---------------------------------------------------------

    def draw_glow(self, painter, x, y, radius, color, alpha=90):
        gradient = QRadialGradient(x, y, radius)

        glow_color = QColor(color)
        glow_color.setAlpha(alpha)

        transparent_color = QColor(color)
        transparent_color.setAlpha(0)

        gradient.setColorAt(0.0, glow_color)
        gradient.setColorAt(1.0, transparent_color)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))

        painter.drawEllipse(
            int(x - radius),
            int(y - radius),
            int(radius * 2),
            int(radius * 2)
        )

    def draw_eye(self, painter, x, y, width, height, color, pulse):
        eye_height = height * (0.85 + pulse * 0.15)

        # Soft glow behind the eye.
        self.draw_glow(
            painter,
            x,
            y,
            width * 1.8,
            color,
            90
        )

        # Dark recessed eye socket.
        painter.setPen(
            QPen(QColor("#07111F"), 2)
        )

        painter.setBrush(
            QColor("#050B14")
        )

        painter.drawRoundedRect(
            int(x - width / 2 - 4),
            int(y - height / 2 - 4),
            int(width + 8),
            int(height + 8),
            int(height / 2),
            int(height / 2)
        )

        # Glowing eye.
        eye_gradient = QRadialGradient(
            x,
            y,
            width
        )

        eye_gradient.setColorAt(
            0.0,
            QColor("#FFFFFF")
        )

        eye_gradient.setColorAt(
            0.35,
            QColor(color)
        )

        darker = QColor(color)
        darker = darker.darker(170)

        eye_gradient.setColorAt(
            1.0,
            darker
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(eye_gradient))

        painter.drawRoundedRect(
            int(x - width / 2),
            int(y - eye_height / 2),
            int(width),
            int(eye_height),
            int(eye_height / 2),
            int(eye_height / 2)
        )

        # Small holographic highlight.
        painter.setBrush(
            QColor(255, 255, 255, 190)
        )

        painter.drawEllipse(
            int(x - width * 0.20),
            int(y - eye_height * 0.25),
            int(width * 0.22),
            int(eye_height * 0.22)
        )

    # ---------------------------------------------------------
    # MAIN DRAWING
    # ---------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        painter.fillRect(
            self.rect(),
            QColor("#0B1018")
        )

        center_x = self.width() / 2
        center_y = self.height() / 2

        color = self.get_state_color()

        pulse = (
            math.sin(self.animation_value) + 1
        ) / 2

        # Scale the droid according to the available space.
        scale = min(
            self.width() / 300,
            self.height() / 300
        )

        scale = max(0.65, min(scale, 1.15))

        head_width = 170 * scale
        head_height = 155 * scale

        head_x = center_x - head_width / 2
        head_y = center_y - head_height / 2

        # -----------------------------------------------------
        # Background stars
        # -----------------------------------------------------

        painter.setPen(Qt.PenStyle.NoPen)

        stars = [
            (0.13, 0.20),
            (0.83, 0.16),
            (0.16, 0.76),
            (0.86, 0.72),
            (0.32, 0.10),
            (0.68, 0.90),
        ]

        for index, (x_ratio, y_ratio) in enumerate(stars):
            twinkle = (
                math.sin(
                    self.animation_value * 1.4 + index
                ) + 1
            ) / 2

            alpha = int(45 + twinkle * 130)

            star_color = QColor(120, 205, 255, alpha)

            painter.setBrush(star_color)

            star_size = 2 + int(twinkle * 2)

            painter.drawEllipse(
                int(self.width() * x_ratio),
                int(self.height() * y_ratio),
                star_size,
                star_size
            )

        # -----------------------------------------------------
        # Holographic aura
        # -----------------------------------------------------

        aura_radius = head_width * (
            0.90 + pulse * 0.12
        )

        self.draw_glow(
            painter,
            center_x,
            center_y,
            aura_radius,
            color,
            55
        )

        # -----------------------------------------------------
        # Rotating holographic rings
        # -----------------------------------------------------

        painter.save()

        painter.translate(center_x, center_y)

        painter.rotate(
            math.degrees(self.animation_value * 0.45)
        )

        ring_pen = QPen(
            QColor(
                color.red(),
                color.green(),
                color.blue(),
                130
            ),
            2
        )

        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawEllipse(
            int(-head_width * 0.72),
            int(-head_height * 0.30),
            int(head_width * 1.44),
            int(head_height * 0.60)
        )

        painter.restore()

        painter.save()

        painter.translate(center_x, center_y)

        painter.rotate(
            -math.degrees(self.animation_value * 0.30)
        )

        second_ring_pen = QPen(
            QColor(
                color.red(),
                color.green(),
                color.blue(),
                75
            ),
            1
        )

        second_ring_pen.setStyle(
            Qt.PenStyle.DashLine
        )

        painter.setPen(second_ring_pen)

        painter.drawEllipse(
            int(-head_width * 0.82),
            int(-head_width * 0.82),
            int(head_width * 1.64),
            int(head_width * 1.64)
        )

        painter.restore()

        # -----------------------------------------------------
        # Side antennae
        # -----------------------------------------------------

        antenna_y = head_y + head_height * 0.35

        painter.setPen(
            QPen(QColor("#54718D"), 5)
        )

        painter.drawLine(
            int(head_x + 8),
            int(antenna_y),
            int(head_x - 13 * scale),
            int(antenna_y - 13 * scale)
        )

        painter.drawLine(
            int(head_x + head_width - 8),
            int(antenna_y),
            int(head_x + head_width + 13 * scale),
            int(antenna_y - 13 * scale)
        )

        # Antenna lights.
        antenna_alpha = 110
        if self.state == "listening":
            antenna_alpha = int(80 + pulse * 150)
        elif self.state == "speaking":
            antenna_alpha = int(90 + pulse * 80)
        elif self.state == "error":
            antenna_alpha = 200 if pulse > 0.5 else 40

        self.draw_glow(
            painter,
            head_x - 13 * scale,
            antenna_y - 13 * scale,
            13 * scale,
            color,
            antenna_alpha
        )

        self.draw_glow(
            painter,
            head_x + head_width + 13 * scale,
            antenna_y - 13 * scale,
            13 * scale,
            color,
            antenna_alpha
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)

        painter.drawEllipse(
            int(head_x - 17 * scale),
            int(antenna_y - 17 * scale),
            int(8 * scale),
            int(8 * scale)
        )

        painter.drawEllipse(
            int(head_x + head_width + 9 * scale),
            int(antenna_y - 17 * scale),
            int(8 * scale),
            int(8 * scale)
        )

        # -----------------------------------------------------
        # Droid head shadow
        # -----------------------------------------------------

        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(
            QColor(0, 0, 0, 120)
        )

        painter.drawRoundedRect(
            int(head_x - 5 * scale),
            int(head_y + 7 * scale),
            int(head_width + 10 * scale),
            int(head_height + 10 * scale),
            int(42 * scale),
            int(42 * scale)
        )

        # -----------------------------------------------------
        # Main droid head
        # -----------------------------------------------------

        head_gradient = QRadialGradient(
            center_x - head_width * 0.25,
            head_y + head_height * 0.18,
            head_width * 1.25
        )

        head_gradient.setColorAt(
            0.0,
            QColor("#34475E")
        )

        head_gradient.setColorAt(
            0.55,
            QColor("#1A2A3D")
        )

        head_gradient.setColorAt(
            1.0,
            QColor("#080F19")
        )

        painter.setBrush(QBrush(head_gradient))

        painter.setPen(
            QPen(QColor("#54718D"), 2)
        )

        painter.drawRoundedRect(
            int(head_x),
            int(head_y),
            int(head_width),
            int(head_height),
            int(38 * scale),
            int(38 * scale)
        )

        # -----------------------------------------------------
        # Holographic outline
        # -----------------------------------------------------

        outline_color = QColor(color)
        outline_color.setAlpha(
            int(110 + pulse * 100)
        )

        painter.setPen(
            QPen(outline_color, 2)
        )

        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRoundedRect(
            int(head_x + 5 * scale),
            int(head_y + 5 * scale),
            int(head_width - 10 * scale),
            int(head_height - 10 * scale),
            int(34 * scale),
            int(34 * scale)
        )

        # -----------------------------------------------------
        # Forehead panel
        # -----------------------------------------------------

        panel_width = head_width * 0.40
        panel_height = 10 * scale

        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(
            QColor("#0A1523")
        )

        painter.drawRoundedRect(
            int(center_x - panel_width / 2),
            int(head_y + 17 * scale),
            int(panel_width),
            int(panel_height),
            int(5 * scale),
            int(5 * scale)
        )

        # Moving forehead light.
        light_x = (
            center_x
            + math.sin(self.animation_value) * panel_width * 0.30
        )

        self.draw_glow(
            painter,
            light_x,
            head_y + 22 * scale,
            12 * scale,
            color,
            150
        )

        painter.setBrush(color)

        painter.drawEllipse(
            int(light_x - 3 * scale),
            int(head_y + 19 * scale),
            int(6 * scale),
            int(6 * scale)
        )

        # -----------------------------------------------------
        # Face visor
        # -----------------------------------------------------

        visor_width = head_width * 0.78
        visor_height = head_height * 0.48

        visor_x = center_x - visor_width / 2
        visor_y = center_y - visor_height * 0.30

        visor_gradient = QRadialGradient(
            center_x,
            visor_y + visor_height / 2,
            visor_width * 0.8
        )

        visor_gradient.setColorAt(
            0.0,
            QColor("#102C43")
        )

        visor_gradient.setColorAt(
            0.75,
            QColor("#071522")
        )

        visor_gradient.setColorAt(
            1.0,
            QColor("#030912")
        )

        painter.setBrush(QBrush(visor_gradient))

        painter.setPen(
            QPen(QColor("#34516C"), 2)
        )

        painter.drawRoundedRect(
            int(visor_x),
            int(visor_y),
            int(visor_width),
            int(visor_height),
            int(24 * scale),
            int(24 * scale)
        )

        # Visor edge glow.
        visor_outline = QColor(color)
        visor_outline.setAlpha(110)

        painter.setPen(
            QPen(visor_outline, 1)
        )

        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRoundedRect(
            int(visor_x + 4 * scale),
            int(visor_y + 4 * scale),
            int(visor_width - 8 * scale),
            int(visor_height - 8 * scale),
            int(20 * scale),
            int(20 * scale)
        )

        # -----------------------------------------------------
        # Droid eyes
        # -----------------------------------------------------

        eye_y = visor_y + visor_height * 0.43

        eye_width = 31 * scale
        eye_height = 25 * scale

        eye_spacing = visor_width * 0.27

        left_eye_x = center_x - eye_spacing / 2
        right_eye_x = center_x + eye_spacing / 2

        # Friendly expression: eyes remain open.
        # Listening gives the eyes a brighter pulse.
        eye_pulse = pulse
        look = 0
        blink = self.state == "idle" and pulse < 0.08

        if self.state == "listening":
            eye_pulse = 1.0
            look = 8 * scale * math.sin(self.animation_value * 1.4)
        elif self.state == "thinking":
            eye_pulse = 0.45 + pulse * 0.55
        elif self.state == "speaking":
            eye_pulse = 0.9
        elif self.state == "error":
            eye_pulse = 0.25
        if blink:
            eye_pulse = 0.08

        self.draw_eye(
            painter,
            left_eye_x + look,
            eye_y,
            eye_width,
            eye_height,
            color,
            eye_pulse
        )

        self.draw_eye(
            painter,
            right_eye_x + look,
            eye_y,
            eye_width,
            eye_height,
            color,
            eye_pulse
        )

        # -----------------------------------------------------
        # Mouth / voice indicator
        # -----------------------------------------------------

        mouth_y = visor_y + visor_height * 0.78

        if self.state == "speaking":
            mouth_open = (6 + pulse * 10) * scale
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(
                int(center_x - 12 * scale),
                int(mouth_y - mouth_open / 2),
                int(24 * scale),
                int(mouth_open),
                int(6 * scale),
                int(6 * scale)
            )
            bar_count = 5
            bar_width = 4 * scale
            bar_gap = 7 * scale

            total_width = (
                bar_count * bar_width
                + (bar_count - 1) * bar_gap
            )

            start_x = center_x - total_width / 2

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#FFFFFF"))

            for index in range(bar_count):
                bar_height = (
                    5 * scale
                    + abs(
                        math.sin(
                            self.animation_value * 2
                            + index * 0.9
                        )
                    ) * 13 * scale
                )

                x = start_x + index * (
                    bar_width + bar_gap
                )

                painter.drawRoundedRect(
                    int(x),
                    int(mouth_y - bar_height / 2),
                    int(bar_width),
                    int(bar_height),
                    int(2 * scale),
                    int(2 * scale)
                )

        elif self.state == "listening":

            # Listening indicator: a small microphone glyph.
            painter.setPen(
                QPen(QColor("#FFFFFF"), 2 * scale)
            )

            painter.setBrush(Qt.BrushStyle.NoBrush)

            mic_width = 10 * scale
            mic_height = 14 * scale

            painter.drawRoundedRect(
                int(center_x - mic_width / 2),
                int(mouth_y - mic_height / 2),
                int(mic_width),
                int(mic_height),
                int(5 * scale),
                int(5 * scale)
            )

            painter.drawArc(
                int(center_x - 10 * scale),
                int(mouth_y - 2 * scale),
                int(20 * scale),
                int(17 * scale),
                0,
                -180 * 16
            )

            painter.drawLine(
                int(center_x),
                int(mouth_y + 12 * scale),
                int(center_x),
                int(mouth_y + 17 * scale)
            )

        elif self.state == "thinking":

            # Three moving dots while processing.
            for index in range(3):
                angle = (
                    self.animation_value * 1.5
                    + index * math.pi * 2 / 3
                )

                dot_distance = 9 * scale

                dot_x = (
                    center_x
                    + math.cos(angle) * dot_distance
                )

                dot_y = (
                    mouth_y
                    + math.sin(angle) * dot_distance
                )

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#FFFFFF"))

                painter.drawEllipse(
                    int(dot_x - 3 * scale),
                    int(dot_y - 3 * scale),
                    int(6 * scale),
                    int(6 * scale)
                )

        elif self.state == "error":

            # Small X indicator.
            painter.setPen(
                QPen(QColor("#FF4D6D"), 2 * scale)
            )

            painter.drawLine(
                int(center_x - 6 * scale),
                int(mouth_y - 6 * scale),
                int(center_x + 6 * scale),
                int(mouth_y + 6 * scale)
            )

            painter.drawLine(
                int(center_x + 6 * scale),
                int(mouth_y - 6 * scale),
                int(center_x - 6 * scale),
                int(mouth_y + 6 * scale)
            )

        else:

            # Friendly idle smile.
            painter.setPen(
                QPen(color, 2 * scale)
            )

            painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.drawArc(
                int(center_x - 12 * scale),
                int(mouth_y - 8 * scale),
                int(24 * scale),
                int(15 * scale),
                200 * 16,
                140 * 16
            )

        # -----------------------------------------------------
        # Lower chin panel
        # -----------------------------------------------------

        chin_y = head_y + head_height - 20 * scale

        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(
            QColor("#101C2B")
        )

        painter.drawRoundedRect(
            int(center_x - 30 * scale),
            int(chin_y),
            int(60 * scale),
            int(8 * scale),
            int(4 * scale),
            int(4 * scale)
        )

        # Three tiny status lights.
        for index in range(3):
            light_x = center_x + (
                index - 1
            ) * 13 * scale

            light_color = QColor(color)

            if self.state == "error":
                light_color = QColor("#FF4D6D")

            light_color.setAlpha(
                int(100 + pulse * 155)
            )

            painter.setBrush(light_color)

            painter.drawEllipse(
                int(light_x - 2 * scale),
                int(chin_y + 2 * scale),
                int(4 * scale),
                int(4 * scale)
            )

        # -----------------------------------------------------
        # Floating holographic indicator
        # -----------------------------------------------------

        indicator_angle = self.animation_value * 1.4
        indicator_distance = head_width * 0.88

        indicator_x = (
            center_x
            + math.cos(indicator_angle) * indicator_distance
        )

        indicator_y = (
            center_y
            + math.sin(indicator_angle) * indicator_distance * 0.65
        )

        self.draw_glow(
            painter,
            indicator_x,
            indicator_y,
            12 * scale,
            color,
            130
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)

        painter.drawEllipse(
            int(indicator_x - 4 * scale),
            int(indicator_y - 4 * scale),
            int(8 * scale),
            int(8 * scale)
        )

        painter.end()