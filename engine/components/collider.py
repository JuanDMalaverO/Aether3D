"""
Collider — forma de colisión asociada a una entidad.

shape = "aabb"   → caja alineada con los ejes; parámetro relevante: size
shape = "sphere" → esfera; parámetro relevante: radius
offset           → desplazamiento respecto al origen de la entidad (espacio local)
"""
from dataclasses import dataclass, field
import numpy as np


@dataclass
class Collider:
    shape:  str        = "aabb"
    size:   np.ndarray = field(default_factory=lambda: np.ones(3,  dtype=np.float32))
    radius: float      = 0.5
    offset: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float32))
