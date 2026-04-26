"""
Rigidbody — componente de físicas de cuerpo rígido.
"""
from dataclasses import dataclass, field
import numpy as np


@dataclass
class Rigidbody:
    mass:         float      = 1.0
    velocity:     np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float32))
    acceleration: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float32))
    use_gravity:  bool       = True
    is_static:    bool       = False
    restitution:  float      = 0.4    # coeficiente de rebote [0=inelástico, 1=perfectamente elástico]
    friction:     float      = 0.5    # amortiguación de contacto [0=sin fricción, 1=máxima]
