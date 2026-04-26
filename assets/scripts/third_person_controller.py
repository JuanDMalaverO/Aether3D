"""
ThirdPersonController — posiciona una entidad Camera detrás y encima de un objetivo.

Asigna este script a la entidad que tenga el componente Camera.
El script busca automáticamente la entidad cuyo nombre contenga `target_name`.

Atributos configurables:
    target_name  — substring del nombre de la entidad objetivo (default "Jugador")
    distance     — distancia horizontal al objetivo
    height       — altura adicional por encima del objetivo
    sensitivity  — sensibilidad del mouse (grados/píxel)
    lerp_speed   — velocidad de seguimiento suavizado (mayor = más rápido)
"""
from engine.scripting import BaseScript
from engine.components import Transform
from engine.input import Input
import numpy as np


class ThirdPersonController(BaseScript):
    target_name: str   = "Jugador"
    distance:    float = 5.0
    height:      float = 2.0
    sensitivity: float = 0.15
    lerp_speed:  float = 8.0

    def on_start(self, entity: int, world) -> None:
        self._yaw   = 0.0
        self._pitch = 20.0
        self._target_eid = None

    def on_update(self, entity: int, world, dt: float) -> None:
        # Buscar objetivo (cacheado para eficiencia)
        if self._target_eid is None or world.get_component(self._target_eid, Transform) is None:
            for eid in world.all_entities():
                if self.target_name in world.get_entity_name(eid):
                    self._target_eid = eid
                    break
        if self._target_eid is None:
            return

        target_tr = world.get_component(self._target_eid, Transform)
        cam_tr    = world.get_component(entity, Transform)
        if target_tr is None or cam_tr is None:
            return

        # Rotar con el mouse
        dx, dy = Input.get_mouse_delta()
        self._yaw   -= dx * self.sensitivity
        self._pitch  = max(-30.0, min(80.0, self._pitch + dy * self.sensitivity))

        yr = np.radians(self._yaw)
        pr = np.radians(self._pitch)

        # Posición deseada en esfera alrededor del objetivo
        offset = np.array([
            self.distance * np.cos(pr) * np.sin(yr),
            self.distance * np.sin(pr) + self.height,
            self.distance * np.cos(pr) * np.cos(yr),
        ], np.float32)
        desired = target_tr.position.astype(np.float32) + offset

        # Suavizado (lerp)
        t = min(1.0, self.lerp_speed * dt)
        cam_tr.position[:] = cam_tr.position + (desired - cam_tr.position) * t

        # Apuntar al objetivo
        look_target = target_tr.position.astype(np.float32)
        fwd = look_target - cam_tr.position
        dist = float(np.linalg.norm(fwd))
        if dist > 1e-4:
            fwd /= dist
            cam_tr.rotation[0] = float(np.degrees(np.arcsin(np.clip(fwd[1], -1.0, 1.0))))
            cam_tr.rotation[1] = float(np.degrees(np.arctan2(fwd[0], fwd[2])))
