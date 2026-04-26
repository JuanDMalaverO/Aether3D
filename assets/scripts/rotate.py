"""
rotate.py — rota el objeto continuamente alrededor del eje Y.

Parámetros editables:
    speed  → grados por segundo (positivo = sentido antihorario visto desde arriba)
    axis   → índice del eje de rotación (0=X, 1=Y, 2=Z)
"""
from engine.scripting import BaseScript
from engine.components import Transform


class RotateScript(BaseScript):
    def __init__(self):
        self.speed = 90.0   # grados / segundo
        self.axis  = 1      # 0=X, 1=Y, 2=Z

    def on_start(self, entity, world):
        print(f"[RotateScript] Iniciado en entidad {entity}")

    def on_update(self, entity, world, dt):
        t = world.get_component(entity, Transform)
        if t is not None:
            t.rotation[self.axis] = (t.rotation[self.axis] + self.speed * dt) % 360.0
