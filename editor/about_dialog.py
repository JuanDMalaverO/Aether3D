"""
AboutDialog — Créditos y detalles de Aether3D.

© 2026 Juan Malaver. Todos los derechos reservados.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor


class AboutDialog(QDialog):
    """Diálogo de créditos — Aether3D · Juan Malaver."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Acerca de Aether3D")
        self.setFixedSize(520, 460)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background: #09090e;
                border: 1px solid #1e1e2c;
            }
        """)
        self._build()

    def _build(self):
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

        # Cuerpo
        body = QVBoxLayout()
        body.setContentsMargins(44, 36, 44, 36)
        body.setSpacing(0)
        root.addLayout(body, 1)

        # Título
        title = QLabel("AETHER3D")
        title.setStyleSheet(
            "color: #e8e8f8; font-size: 32px; font-weight: 700;"
            "letter-spacing: 0.14em; border: none;"
        )
        body.addWidget(title)

        sub = QLabel("3D Engine  &  Editor")
        sub.setStyleSheet(
            "color: #6c63ff; font-size: 12px; letter-spacing: 0.18em;"
            "border: none; padding-top: 2px;"
        )
        body.addWidget(sub)

        body.addSpacing(6)

        ver = QLabel("Versión 1.0  ·  OpenGL 3.3 Core Profile")
        ver.setStyleSheet("color: #28283c; font-size: 11px; border: none;")
        body.addWidget(ver)

        body.addSpacing(32)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("QFrame { background: #14142a; border: none; }")
        body.addWidget(sep)

        body.addSpacing(24)

        # Autor principal
        self._row(body, "Desarrollado por",
                  "Juan Malaver", highlight=True)
        body.addSpacing(20)

        # Sistemas
        self._section(body, "ARQUITECTURA Y SISTEMAS")
        for sistem in [
            "Motor de rendering PBR — Cook-Torrance GGX + IBL",
            "ECS (Entity Component System) — arquitectura desde cero",
            "Sistema de física — AABB · Sphere · impulsos · colisiones",
            "Scripting — Python por entidad con hot-reload",
            "Partículas GPU — GPU instancing, billboards, presets JSON",
            "Cámaras múltiples — FPS, tercera persona, ortográfica",
            "Editor 3D — inspector, jerarquía drag-drop, gizmos, picking",
            "Shadow mapping · Post-processing ACES · Skybox IBL",
        ]:
            lbl = QLabel(f"  ·  {sistem}")
            lbl.setStyleSheet("color: #38385a; font-size: 11px; border: none; padding: 2px 0;")
            body.addWidget(lbl)

        body.addSpacing(20)
        self._section(body, "TECNOLOGÍAS")
        tech_lbl = QLabel(
            "Python 3.12  ·  PyQt6  ·  PyOpenGL  ·  numpy  ·  pyrr  ·  Pillow"
        )
        tech_lbl.setStyleSheet("color: #28284a; font-size: 11px; border: none; padding-top: 4px;")
        body.addWidget(tech_lbl)

        body.addStretch(1)

        # Copyright
        copy_lbl = QLabel("© 2026 Juan Malaver — Todos los derechos reservados")
        copy_lbl.setStyleSheet(
            "color: #1e1e34; font-size: 10px; border: none; padding-top: 16px;"
        )
        body.addWidget(copy_lbl)

        # Barra inferior con botón cerrar
        root.addWidget(self._footer())

    def _row(self, parent_lay: QVBoxLayout, label: str, value: str, highlight=False):
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #28284a; font-size: 11px; border: none; min-width: 100px;")
        row.addWidget(lbl)
        val = QLabel(value)
        color = "#c4bcff" if highlight else "#7070a0"
        weight = "600" if highlight else "400"
        size = "14px" if highlight else "12px"
        val.setStyleSheet(
            f"color: {color}; font-size: {size}; font-weight: {weight}; border: none;"
        )
        row.addWidget(val)
        row.addStretch(1)
        parent_lay.addLayout(row)

    def _section(self, parent_lay: QVBoxLayout, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #24243e; font-size: 9px; font-weight: 600;"
            "letter-spacing: 0.14em; border: none; padding-bottom: 6px;"
        )
        parent_lay.addWidget(lbl)

    def _footer(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet(
            "QFrame { background: #050509; border: none; border-top: 1px solid #12121e; }"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(24, 0, 24, 0)

        credits = QLabel("Juan Malaver  ·  Aether3D Engine")
        credits.setStyleSheet("color: #1a1a30; font-size: 10px; border: none;")
        lay.addWidget(credits)

        lay.addStretch(1)

        close_btn = QPushButton("Cerrar")
        close_btn.setFixedSize(88, 34)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet(
            "QPushButton {"
            "  background: #111120; color: #6060a0;"
            "  border: 1px solid #2a2a40; border-radius: 6px;"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover { background: #6c63ff22; border-color: #6c63ff66; color: #c4bcff; }"
        )
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)

        return bar
