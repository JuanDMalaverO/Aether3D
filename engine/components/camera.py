"""
Camera - Parámetros de cámara. La posición/rotación la maneja el Transform.
"""
from dataclasses import dataclass


@dataclass
class Camera:
    fov: float = 60.0               # Grados (solo perspectiva)
    near: float = 0.1
    far: float = 1000.0
    projection: str = "perspective"  # "perspective" | "orthographic"
    ortho_size: float = 10.0         # Alto del frustum ortográfico en unidades mundo
    is_main: bool = True             # Cámara principal usada en Play mode
