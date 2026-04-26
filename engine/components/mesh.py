"""
MeshRenderer - Referencia a una malla y un material (color por ahora).
"""
from dataclasses import dataclass, field
import numpy as np


@dataclass
class MeshRenderer:
    mesh_name: str = "cube"  # Identificador de la malla en el registro
    color: np.ndarray = field(default_factory=lambda: np.array([0.8, 0.8, 0.8], dtype=np.float32))
    visible: bool = True
