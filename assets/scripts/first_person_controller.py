"""
FirstPersonController — controla una entidad Camera en primera persona.

Asigna este script a la entidad que tenga el componente Camera (con is_main=True).
La entidad necesita también un Transform. En fly_mode=True no necesita Rigidbody.

Atributos configurables (editar directamente en el código o desde inspector en futuras versiones):
    speed        — velocidad de movimiento en unidades/segundo
    sensitivity  — sensibilidad del ratón
    fly_mode     — True: movimiento libre en 3D sin física
"""
from engine.scripting import BaseScript
from engine.components import Transform, Rigidbody
from engine.input import Input
import numpy as np


class FirstPersonController(BaseScript):
    speed:       float = 5.0
    sensitivity: float = 0.12
    fly_mode:    bool  = True

    def on_start(self, entity: int, world) -> None:
        self._yaw   = 0.0
        self._pitch = 0.0
        tr = world.get_component(entity, Transform)
        if tr is not None:
            self._yaw   = float(tr.rotation[1])
            self._pitch = float(tr.rotation[0])

    def on_update(self, entity: int, world, dt: float) -> None:
        tr = world.get_component(entity, Transform)
        if tr is None:
            return

        # Rotar con el mouse
        dx, dy = Input.get_mouse_delta()
        self._yaw   -= dx * self.sensitivity
        self._pitch  = max(-89.0, min(89.0, self._pitch - dy * self.sensitivity))
        tr.rotation[0] = self._pitch
        tr.rotation[1] = self._yaw

        # Vectores de movimiento (basados en yaw, sin pitch para WASD horizontal)
        yr = np.radians(self._yaw)
        pr = np.radians(self._pitch)
        fwd   = np.array([ np.cos(pr)*np.sin(yr), np.sin(pr),  np.cos(pr)*np.cos(yr)], np.float32)
        right = np.array([-np.cos(yr),             0,           np.sin(yr)],            np.float32)
        up    = np.array([0, 1, 0], np.float32)

        if self.fly_mode:
            delta = np.zeros(3, np.float32)
            spd = self.speed * dt
            if Input.get_key("W"):     delta += fwd   * spd
            if Input.get_key("S"):     delta -= fwd   * spd
            if Input.get_key("D"):     delta += right * spd
            if Input.get_key("A"):     delta -= right * spd
            if Input.get_key("SPACE"): delta += up    * spd
            if Input.get_key("CTRL"):  delta -= up    * spd
            tr.position += delta
        else:
            # Con física: controla velocidad del Rigidbody horizontalmente
            rb = world.get_component(entity, Rigidbody)
            if rb is not None:
                flat_fwd   = np.array([np.sin(yr), 0, np.cos(yr)], np.float32)
                flat_right = np.array([-np.cos(yr), 0, np.sin(yr)], np.float32)
                spd = self.speed
                vx = vz = 0.0
                if Input.get_key("W"): vx += flat_fwd[0]*spd;   vz += flat_fwd[2]*spd
                if Input.get_key("S"): vx -= flat_fwd[0]*spd;   vz -= flat_fwd[2]*spd
                if Input.get_key("D"): vx += flat_right[0]*spd; vz += flat_right[2]*spd
                if Input.get_key("A"): vx -= flat_right[0]*spd; vz -= flat_right[2]*spd
                rb.velocity[0] = vx
                rb.velocity[2] = vz
                if Input.get_key("SPACE") and abs(float(rb.velocity[1])) < 0.8:
                    rb.velocity[1] = 7.0
