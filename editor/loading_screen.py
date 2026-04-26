"""
LoadingScreen — Overlay de carga elegante para Aether3D.
Se muestra mientras el motor inicializa shaders, meshes e IBL.

Desarrollado por Juan Malaver.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QFrame, QApplication
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QCursor


class LoadingScreen(QDialog):
    """Pantalla de carga frameless — Aether3D · Juan Malaver."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(480, 240)
        self._center()
        self._dot_count = 0
        self._build()

        # Animar los puntos cada 400ms
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(400)

    def _build(self):
        self.setStyleSheet("""
            QDialog {
                background: #09090e;
                border: 1px solid #1e1e2c;
                border-radius: 10px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Barra de acento superior
        accent = QFrame()
        accent.setFixedHeight(3)
        accent.setStyleSheet(
            "QFrame { background: qlineargradient("
            "  x1:0,y1:0,x2:1,y2:0,"
            "  stop:0 #3d35c8, stop:0.5 #6c63ff, stop:1 #a89bff"
            "); border: none; }"
        )
        root.addWidget(accent)

        # Cuerpo central
        body = QVBoxLayout()
        body.setContentsMargins(48, 40, 48, 40)
        body.setSpacing(0)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addLayout(body, 1)

        # Logo
        logo = QLabel("AETHER3D")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            "color: #e8e8f8;"
            "font-size: 30px;"
            "font-weight: 700;"
            "letter-spacing: 0.14em;"
            "border: none;"
        )
        body.addWidget(logo)

        # Subtítulo
        sub = QLabel("3D Engine  &  Editor")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            "color: #6c63ff;"
            "font-size: 11px;"
            "letter-spacing: 0.18em;"
            "border: none;"
            "padding-top: 2px;"
        )
        body.addWidget(sub)

        body.addSpacing(28)

        # Barra de progreso (decorativa, animada con CSS)
        bar_wrap = QFrame()
        bar_wrap.setFixedHeight(3)
        bar_wrap.setStyleSheet(
            "QFrame { background: #1a1a28; border: none; border-radius: 2px; }"
        )
        body.addWidget(bar_wrap)

        body.addSpacing(18)

        # Estado actual
        self._status = QLabel("Iniciando motor")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(
            "color: #50507a;"
            "font-size: 11px;"
            "letter-spacing: 0.06em;"
            "border: none;"
        )
        body.addWidget(self._status)

        # Barra de créditos inferior
        footer = QFrame()
        footer.setFixedHeight(36)
        footer.setStyleSheet(
            "QFrame { background: #050509; border: none; border-top: 1px solid #12121e; }"
        )
        foot_lay = QVBoxLayout(footer)
        foot_lay.setContentsMargins(0, 0, 0, 0)
        credit = QLabel("Desarrollado por  Juan Malaver")
        credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit.setStyleSheet("color: #1c1c34; font-size: 10px; border: none;")
        foot_lay.addWidget(credit)
        root.addWidget(footer)

    def set_status(self, text: str) -> None:
        self._status.setText(text)
        QApplication.processEvents()

    def _tick(self):
        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count
        base = self._status.text().rstrip(".")
        self._status.setText(base + dots)

    def _center(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width()  - self.width())  // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
