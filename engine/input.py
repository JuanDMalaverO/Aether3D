"""
Input — singleton de lectura de teclado y ratón accesible desde scripts.
El viewport actualiza este estado cada frame durante el modo Play.

Uso en scripts:
    from engine.input import Input
    if Input.get_key("W"):    # mover adelante
    dx, dy = Input.get_mouse_delta()
"""


class Input:
    _keys:     set   = set()   # conjunto de nombres de tecla en mayúsculas
    _mouse_dx: float = 0.0
    _mouse_dy: float = 0.0

    @classmethod
    def get_key(cls, key: str) -> bool:
        """Devuelve True si la tecla está presionada. Nombres: "W","A","S","D","SPACE","SHIFT","CTRL","Q","E","R","F"."""
        return key.upper() in cls._keys

    @classmethod
    def get_mouse_delta(cls) -> tuple[float, float]:
        """Devuelve el delta del mouse (dx, dy) del frame actual."""
        return cls._mouse_dx, cls._mouse_dy

    # ── Métodos internos (llamados por el viewport, no por scripts) ────────
    @classmethod
    def _set_keys(cls, qt_keys: set) -> None:
        from PyQt6.QtCore import Qt
        _map = {
            Qt.Key.Key_W:       "W",
            Qt.Key.Key_A:       "A",
            Qt.Key.Key_S:       "S",
            Qt.Key.Key_D:       "D",
            Qt.Key.Key_Space:   "SPACE",
            Qt.Key.Key_Shift:   "SHIFT",
            Qt.Key.Key_Control: "CTRL",
            Qt.Key.Key_Q:       "Q",
            Qt.Key.Key_E:       "E",
            Qt.Key.Key_R:       "R",
            Qt.Key.Key_F:       "F",
        }
        cls._keys = {_map[k] for k in qt_keys if k in _map}

    @classmethod
    def _set_mouse_delta(cls, dx: float, dy: float) -> None:
        cls._mouse_dx = dx
        cls._mouse_dy = dy

    @classmethod
    def _clear_mouse_delta(cls) -> None:
        cls._mouse_dx = 0.0
        cls._mouse_dy = 0.0
