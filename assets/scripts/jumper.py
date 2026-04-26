"""
jumper.py — hace que el objeto salte automáticamente al detectar colisión con el suelo.

El salto se activa cuando la entidad tiene un Rigidbody con velocidad vertical
pequeña (está en el suelo o acaba de aterrizar) y colisiona con cualquier otro
objeto.  Ideal para pelota/cubo con física.

Parámetros:
    jump_speed   → velocidad vertical del salto (m/s)
    v_threshold  → umbral de velocidad vertical para considerar "en el suelo"
"""
from engine.scripting import BaseScript
from engine.components import Rigidbody


class JumperScript(BaseScript):
    def __init__(self):
        self.jump_speed  = 8.0
        self.v_threshold = 1.0   # m/s: si |vy| < threshold → saltar

    def on_start(self, entity, world):
        print(f"[JumperScript] Iniciado en entidad {entity}")

    def on_collision(self, entity, other_entity, world):
        rb = world.get_component(entity, Rigidbody)
        if rb is None or rb.is_static:
            return
        # Saltar solo si la entidad está cerca del suelo (velocidad Y pequeña)
        if abs(float(rb.velocity[1])) < self.v_threshold:
            rb.velocity[1] = float(self.jump_speed)
