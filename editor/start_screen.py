"""
StartScreen — Pantalla de inicio de Aether3D.

Muestra la marca, botones de acción y escenas recientes antes de
abrir el editor. Diseñada sin decoraciones de sistema operativo
para un aspecto limpio y elegante.

Desarrollado por Juan Malaver.
"""
import os
import json
import datetime
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QFileDialog,
    QScrollArea, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor

_RECENT_FILE = os.path.join(os.path.dirname(__file__), "..", ".aether3d_recent.json")
_MAX_RECENT  = 8


# ── Utilidad de recientes ──────────────────────────────────────────────────

def _load_recent() -> list[dict]:
    try:
        with open(_RECENT_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return [r for r in data if os.path.isfile(r.get("path", ""))]
    except Exception:
        return []


def _save_recent(path: str) -> None:
    entries = _load_recent()
    entries = [e for e in entries if e["path"] != path]
    entries.insert(0, {
        "path": path,
        "name": os.path.splitext(os.path.basename(path))[0],
        "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
    })
    entries = entries[:_MAX_RECENT]
    try:
        with open(_RECENT_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def record_opened_scene(path: str) -> None:
    """Llamar desde MainWindow cuando se abre una escena."""
    _save_recent(path)


# ── Widget de escena reciente ──────────────────────────────────────────────

class _RecentItem(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, entry: dict):
        super().__init__()
        self._path = entry["path"]
        self.setFixedHeight(52)
        self.setStyleSheet(
            "QFrame { background: transparent; border: none; border-radius: 6px; }"
            "QFrame:hover { background: #6c63ff14; }"
        )
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)

        name_lbl = QLabel(entry.get("name", "Escena"))
        name_lbl.setStyleSheet(
            "color: #c0c0d8; font-size: 12px; font-weight: 500; border: none; background: transparent;"
        )
        lay.addWidget(name_lbl)

        meta = QLabel(f"{entry.get('date', '')}  ·  {entry['path']}")
        meta.setStyleSheet(
            "color: #40405a; font-size: 10px; border: none; background: transparent;"
        )
        meta.setElideMode(Qt.TextElideMode.ElideMiddle)
        lay.addWidget(meta)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path)


# ── Pantalla principal ─────────────────────────────────────────────────────

class StartScreen(QDialog):
    """Pantalla de inicio — Aether3D · Juan Malaver."""

    new_world_requested  = pyqtSignal()
    load_scene_requested = pyqtSignal(str)   # path

    # Para arrastrar la ventana sin barra de título
    _drag_pos: QPoint | None = None

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(900, 540)
        self._center()
        self._build_ui()

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.setStyleSheet("""
            QDialog {
                background: #09090e;
                border: 1px solid #1e1e2c;
                border-radius: 10px;
            }
        """)

        # Barra de acento superior
        accent = QFrame()
        accent.setFixedHeight(3)
        accent.setStyleSheet(
            "QFrame { background: qlineargradient("
            "  x1:0, y1:0, x2:1, y2:0,"
            "  stop:0 #3d35c8, stop:0.5 #6c63ff, stop:1 #a89bff"
            "); border: none; }"
        )
        root.addWidget(accent)

        # Cuerpo principal
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        body.addWidget(self._build_left_panel())

        # Separador vertical
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("QFrame { background: #1a1a28; border: none; }")
        body.addWidget(sep)

        body.addWidget(self._build_right_panel())

        # Barra de créditos inferior
        root.addWidget(self._build_credits_bar())

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(390)
        panel.setStyleSheet("QWidget { background: #09090e; }")

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(44, 44, 36, 36)
        lay.setSpacing(0)

        # Marca principal
        title = QLabel("AETHER3D")
        title.setStyleSheet(
            "color: #e8e8f8;"
            "font-size: 38px;"
            "font-weight: 700;"
            "letter-spacing: 0.12em;"
            "border: none;"
        )
        lay.addWidget(title)

        sub = QLabel("3D Engine  &  Editor")
        sub.setStyleSheet(
            "color: #6c63ff;"
            "font-size: 13px;"
            "font-weight: 400;"
            "letter-spacing: 0.18em;"
            "border: none;"
            "padding-top: 2px;"
        )
        lay.addWidget(sub)

        ver = QLabel("Versión 1.0")
        ver.setStyleSheet(
            "color: #28283c;"
            "font-size: 11px;"
            "border: none;"
            "padding-top: 4px;"
        )
        lay.addWidget(ver)

        lay.addSpacing(40)

        # Botón Nuevo Mundo
        btn_new = self._action_btn("Nuevo Mundo", primary=True)
        btn_new.clicked.connect(self._on_new)
        lay.addWidget(btn_new)

        lay.addSpacing(10)

        # Botón Cargar Escena
        btn_load = self._action_btn("Cargar Escena…", primary=False)
        btn_load.clicked.connect(self._on_load)
        lay.addWidget(btn_load)

        lay.addStretch(1)

        # Autor
        autor = QLabel("Juan Malaver")
        autor.setStyleSheet(
            "color: #24243a; font-size: 11px; border: none; letter-spacing: 0.04em;"
        )
        lay.addWidget(autor)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("QWidget { background: #07070c; }")

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(28, 32, 28, 28)
        lay.setSpacing(0)

        # Encabezado recientes
        hdr = QLabel("RECIENTES")
        hdr.setStyleSheet(
            "color: #2a2a48;"
            "font-size: 10px;"
            "font-weight: 600;"
            "letter-spacing: 0.14em;"
            "border: none;"
            "padding-bottom: 12px;"
        )
        lay.addWidget(hdr)

        # Lista de escenas recientes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 4px; }"
            "QScrollBar::handle:vertical { background: #1e1e38; border-radius: 2px; }"
        )

        container = QWidget()
        container.setStyleSheet("QWidget { background: transparent; }")
        c_lay = QVBoxLayout(container)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(2)

        recents = _load_recent()
        if recents:
            for entry in recents:
                item = _RecentItem(entry)
                item.clicked.connect(self._on_recent)
                c_lay.addWidget(item)
        else:
            empty = QLabel("Sin escenas recientes")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                "color: #1e1e34; font-size: 12px; border: none; padding: 48px 0;"
            )
            c_lay.addWidget(empty)

        c_lay.addStretch(1)
        scroll.setWidget(container)
        lay.addWidget(scroll, 1)

        return panel

    def _build_credits_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(38)
        bar.setStyleSheet(
            "QFrame { background: #050509; border: none; border-top: 1px solid #12121e; }"
        )

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)

        left = QLabel(
            "Desarrollado íntegramente por  <b style='color:#6c63ff'>Juan Malaver</b>"
        )
        left.setStyleSheet("color: #28284a; font-size: 11px; border: none;")
        lay.addWidget(left)

        lay.addStretch(1)

        right = QLabel(
            "Rendering PBR · Física · Scripting · Partículas GPU · ECS"
            "  ·  © 2026 Juan Malaver"
        )
        right.setStyleSheet("color: #1e1e38; font-size: 10px; border: none;")
        lay.addWidget(right)

        return bar

    # ── Helpers ────────────────────────────────────────────────────────────

    def _action_btn(self, text: str, primary: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(44)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if primary:
            btn.setStyleSheet(
                "QPushButton {"
                "  background: #6c63ff;"
                "  color: #ffffff;"
                "  border: none;"
                "  border-radius: 7px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  letter-spacing: 0.04em;"
                "}"
                "QPushButton:hover { background: #7d75ff; }"
                "QPushButton:pressed { background: #5a52d5; }"
            )
        else:
            btn.setStyleSheet(
                "QPushButton {"
                "  background: #111120;"
                "  color: #7070a0;"
                "  border: 1px solid #2a2a40;"
                "  border-radius: 7px;"
                "  font-size: 13px;"
                "  font-weight: 500;"
                "}"
                "QPushButton:hover {"
                "  background: #6c63ff18;"
                "  border-color: #6c63ff66;"
                "  color: #c4bcff;"
                "}"
                "QPushButton:pressed { background: #6c63ff28; }"
            )
        return btn

    def _center(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width()  - self.width())  // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    # ── Arrastre de ventana ────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── Acciones ───────────────────────────────────────────────────────────

    def _on_new(self):
        self.new_world_requested.emit()
        self.accept()

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar Escena — Aether3D",
            "",
            "Escenas Aether3D (*.json);;Todos los archivos (*)",
        )
        if path:
            _save_recent(path)
            self.load_scene_requested.emit(path)
            self.accept()

    def _on_recent(self, path: str):
        _save_recent(path)
        self.load_scene_requested.emit(path)
        self.accept()
