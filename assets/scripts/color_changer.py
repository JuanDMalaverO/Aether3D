"""
color_changer.py — cambia el color del MeshRenderer aleatoriamente cada segundo.

Parámetros:
    interval   → segundos entre cada cambio de color
    saturation → mínimo de luminosidad por canal (0-1); evita colores muy oscuros
"""
import numpy as np
from engine.scripting import BaseScript
from engine.components import MeshRenderer


class ColorChangerScript(BaseScript):
    def __init__(self):
        self.interval   = 1.0
        self.saturation = 0.25   # valor mínimo de cada canal RGB
        self._timer     = 0.0

    def on_start(self, entity, world):
        print(f"[ColorChangerScript] Iniciado en entidad {entity}")
        self._apply_color(entity, world)

    def on_update(self, entity, world, dt):
        self._timer += dt
        if self._timer >= self.interval:
            self._timer = 0.0
            self._apply_color(entity, world)

    def _apply_color(self, entity, world):
        mr = world.get_component(entity, MeshRenderer)
        if mr is not None:
            mr.color = (np.random.rand(3) * (1.0 - self.saturation)
                        + self.saturation).astype(np.float32)
