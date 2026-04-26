"""
Transform - Posición, rotación (Euler en grados), escala y jerarquía.
"""
from dataclasses import dataclass, field
import numpy as np
import pyrr


@dataclass
class Transform:
    position: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0], dtype=np.float32))
    rotation: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0], dtype=np.float32))  # Euler XYZ grados
    scale: np.ndarray = field(default_factory=lambda: np.array([1.0, 1.0, 1.0], dtype=np.float32))
    parent: int | None = None  # entity_id del padre, None si es raíz

    def local_matrix(self) -> np.ndarray:
        """Calcula la matriz de transformación local (modelo)."""
        t = pyrr.matrix44.create_from_translation(self.position, dtype=np.float32)
        rx = pyrr.matrix44.create_from_x_rotation(np.radians(self.rotation[0]), dtype=np.float32)
        ry = pyrr.matrix44.create_from_y_rotation(np.radians(self.rotation[1]), dtype=np.float32)
        rz = pyrr.matrix44.create_from_z_rotation(np.radians(self.rotation[2]), dtype=np.float32)
        s = pyrr.matrix44.create_from_scale(self.scale, dtype=np.float32)
        # Orden: T * R * S (pyrr usa row-major, así que multiplicamos al revés)
        return s @ rz @ ry @ rx @ t

    def world_matrix(self, world) -> np.ndarray:
        """Matriz mundo: encadena la transformación local con la del padre recursivamente.

        En la convención row-major de pyrr la relación es:
            world = local @ parent_world
        de forma que OpenGL (que transpone al leer) aplica primero el padre.
        """
        local = self.local_matrix()
        if self.parent is None:
            return local
        parent_t = world.get_component(self.parent, Transform)
        if parent_t is None:
            return local
        return local @ parent_t.world_matrix(world)
