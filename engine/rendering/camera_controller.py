"""
OrbitCamera - Cámara orbital estilo Blender/Maya.
- MMB (middle mouse button): rotar alrededor del target
- Shift + MMB: paneo
- Scroll: zoom
"""
import numpy as np
import pyrr


class OrbitCamera:
    def __init__(self):
        self.target = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.distance: float = 8.0
        self.yaw: float = 45.0     # Grados alrededor de Y
        self.pitch: float = 30.0   # Grados de elevación

        self.fov: float = 60.0
        self.near: float = 0.1
        self.far: float = 1000.0

    @property
    def position(self) -> np.ndarray:
        """Calcula la posición de la cámara a partir de yaw/pitch/distance."""
        yaw_r = np.radians(self.yaw)
        pitch_r = np.radians(self.pitch)
        x = self.distance * np.cos(pitch_r) * np.sin(yaw_r)
        y = self.distance * np.sin(pitch_r)
        z = self.distance * np.cos(pitch_r) * np.cos(yaw_r)
        return self.target + np.array([x, y, z], dtype=np.float32)

    def view_matrix(self) -> np.ndarray:
        up = np.array([0, 1, 0], dtype=np.float32)
        return pyrr.matrix44.create_look_at(self.position, self.target, up, dtype=np.float32)

    def projection_matrix(self, aspect: float) -> np.ndarray:
        return pyrr.matrix44.create_perspective_projection(
            self.fov, aspect, self.near, self.far, dtype=np.float32
        )

    # ---------- Interacción ----------
    def orbit(self, dx: float, dy: float, sensitivity: float = 0.4) -> None:
        """Rotar alrededor del target."""
        self.yaw -= dx * sensitivity
        self.pitch += dy * sensitivity
        # Limitar pitch para no invertir la cámara
        self.pitch = max(-89.0, min(89.0, self.pitch))

    def pan(self, dx: float, dy: float) -> None:
        """Mover el target perpendicular a la vista."""
        # Vectores right y up del espacio de cámara
        forward = self.target - self.position
        forward = forward / np.linalg.norm(forward)
        right = np.cross(forward, [0, 1, 0])
        right = right / np.linalg.norm(right)
        up = np.cross(right, forward)

        speed = self.distance * 0.002
        self.target -= right * dx * speed
        self.target += up * dy * speed

    def zoom(self, delta: float) -> None:
        """Acercar o alejar. delta típicamente +1 o -1."""
        factor = 0.9 if delta > 0 else 1.1
        self.distance *= factor
        self.distance = max(0.5, min(500.0, self.distance))
