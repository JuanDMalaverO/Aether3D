"""
Motor 3D - Punto de entrada.

Escena de prueba: física con objetos cayendo y rebotando sobre el suelo.
"""
import os
import sys
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QSurfaceFormat

from engine.ecs import World
from engine.components import Transform, MeshRenderer, Rigidbody, Collider, Script, ParticleEmitter, Material
from engine.rendering import apply_preset
from editor.main_window import MainWindow

_SCRIPTS = os.path.join(os.path.dirname(__file__), "assets", "scripts")


def setup_opengl_format():
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)


_PARTICLES = os.path.join(os.path.dirname(__file__), "assets", "particles")


def create_test_scene(world: World):
    """Escena de física + partículas + jugador en primera persona."""

    # ── Jugador (cápsula) — identidad "Jugador" para que la cámara FPS lo siga
    jugador = world.create_entity("Jugador")
    world.add_component(jugador, Transform(
        position=np.array([0.0, 1.1, 6.0], dtype=np.float32),
        # 1.1 = half_height(0.75) + radius(0.35) ≈ centro de la cápsula con pie en y=0
    ))
    world.add_component(jugador, MeshRenderer(
        mesh_name="capsule",
        color=np.array([0.55, 0.78, 1.0], dtype=np.float32),
    ))
    world.add_component(jugador, Material(
        name="Jugador",
        albedo=np.array([0.55, 0.78, 1.0], np.float32),
        metallic=0.0, roughness=0.5,
    ))
    world.add_component(jugador, Rigidbody(
        mass=75.0, restitution=0.0, friction=0.8,
        use_gravity=True, is_static=False,
    ))
    world.add_component(jugador, Collider(
        shape="sphere", radius=0.38,   # ligeramente mayor que el radio de la cápsula
    ))

    # ── Suelo estático ─────────────────────────────────────────────────
    ground = world.create_entity("Suelo")
    world.add_component(ground, Transform(
        position=np.array([0.0, -0.5, 0.0], dtype=np.float32),
        scale=np.array([20.0, 0.5, 20.0], dtype=np.float32),
    ))
    world.add_component(ground, MeshRenderer(
        mesh_name="cube",
        color=np.array([0.35, 0.35, 0.40], dtype=np.float32),
    ))
    world.add_component(ground, Material(
        name="Suelo",
        albedo=np.array([0.35, 0.35, 0.40], np.float32),
        metallic=0.0, roughness=0.9,
    ))
    world.add_component(ground, Rigidbody(is_static=True, use_gravity=False))
    world.add_component(ground, Collider(
        shape="aabb",
        size=np.array([20.0, 0.5, 20.0], dtype=np.float32),
    ))

    # ── Plataforma elevada estática ────────────────────────────────────
    plat = world.create_entity("Plataforma")
    world.add_component(plat, Transform(
        position=np.array([-4.0, 2.0, 0.0], dtype=np.float32),
        scale=np.array([3.0, 0.3, 3.0], dtype=np.float32),
    ))
    world.add_component(plat, MeshRenderer(
        mesh_name="cube",
        color=np.array([0.4, 0.3, 0.2], dtype=np.float32),
    ))
    world.add_component(plat, Material(
        name="Plataforma",
        albedo=np.array([0.4, 0.3, 0.2], np.float32),
        metallic=0.0, roughness=0.8,
    ))
    world.add_component(plat, Rigidbody(is_static=True, use_gravity=False))
    world.add_component(plat, Collider(
        shape="aabb",
        size=np.array([3.0, 0.3, 3.0], dtype=np.float32),
    ))

    # ── Pelota rebotadora + script Jumper ─────────────────────────────
    b1 = world.create_entity("PelotaRebotadora")
    world.add_component(b1, Transform(
        position=np.array([0.0, 6.0, 0.0], dtype=np.float32),
    ))
    world.add_component(b1, MeshRenderer(
        mesh_name="sphere",
        color=np.array([0.9, 0.2, 0.2], dtype=np.float32),
    ))
    world.add_component(b1, Material(
        name="PelotaRebotadora",
        albedo=np.array([0.9, 0.2, 0.2], np.float32),
        metallic=0.0, roughness=0.3,
    ))
    world.add_component(b1, Rigidbody(
        mass=1.0, restitution=0.85, friction=0.1, use_gravity=True,
    ))
    world.add_component(b1, Collider(shape="sphere", radius=0.5))
    world.add_component(b1, Script(
        path=os.path.join(_SCRIPTS, "jumper.py")
    ))

    # ── Pelota cambia color ────────────────────────────────────────────
    b2 = world.create_entity("PelotaCambiante")
    world.add_component(b2, Transform(
        position=np.array([2.0, 8.0, 0.5], dtype=np.float32),
    ))
    world.add_component(b2, MeshRenderer(
        mesh_name="sphere",
        color=np.array([0.2, 0.7, 0.3], dtype=np.float32),
    ))
    world.add_component(b2, Material(
        name="PelotaCambiante",
        albedo=np.array([0.2, 0.7, 0.3], np.float32),
        metallic=0.0, roughness=0.4,
    ))
    world.add_component(b2, Rigidbody(
        mass=1.0, restitution=0.4, friction=0.4, use_gravity=True,
    ))
    world.add_component(b2, Collider(shape="sphere", radius=0.5))
    world.add_component(b2, Script(
        path=os.path.join(_SCRIPTS, "color_changer.py")
    ))

    # ── Pelota pesada ──────────────────────────────────────────────────
    b3 = world.create_entity("PelotaPesada")
    world.add_component(b3, Transform(
        position=np.array([-2.0, 9.0, -0.5], dtype=np.float32),
    ))
    world.add_component(b3, MeshRenderer(
        mesh_name="sphere",
        color=np.array([0.7, 0.5, 0.1], dtype=np.float32),
    ))
    world.add_component(b3, Material(
        name="PelotaPesada",
        albedo=np.array([0.7, 0.5, 0.1], np.float32),
        metallic=0.8, roughness=0.2,
    ))
    world.add_component(b3, Rigidbody(
        mass=5.0, restitution=0.2, friction=0.6, use_gravity=True,
    ))
    world.add_component(b3, Collider(shape="sphere", radius=0.5))

    # ── Caja giratoria + script Rotate ────────────────────────────────
    box1 = world.create_entity("CajaGiratoria")
    world.add_component(box1, Transform(
        position=np.array([3.5, 5.0, 1.0], dtype=np.float32),
    ))
    world.add_component(box1, MeshRenderer(
        mesh_name="cube",
        color=np.array([0.3, 0.5, 0.9], dtype=np.float32),
    ))
    world.add_component(box1, Material(
        name="CajaGiratoria",
        albedo=np.array([0.3, 0.5, 0.9], np.float32),
        metallic=0.1, roughness=0.5,
    ))
    world.add_component(box1, Rigidbody(
        mass=2.0, restitution=0.3, friction=0.5, use_gravity=True,
    ))
    world.add_component(box1, Collider(
        shape="aabb",
        size=np.array([1.0, 1.0, 1.0], dtype=np.float32),
    ))
    world.add_component(box1, Script(
        path=os.path.join(_SCRIPTS, "rotate.py")
    ))

    # ── Caja pequeña (encima de la plataforma) ─────────────────────────
    box2 = world.create_entity("CajaPequeña")
    world.add_component(box2, Transform(
        position=np.array([-4.0, 3.5, 0.0], dtype=np.float32),
    ))
    world.add_component(box2, MeshRenderer(
        mesh_name="cube",
        color=np.array([0.8, 0.4, 0.8], dtype=np.float32),
    ))
    world.add_component(box2, Material(
        name="CajaPequeña",
        albedo=np.array([0.8, 0.4, 0.8], np.float32),
        metallic=0.0, roughness=0.4,
    ))
    world.add_component(box2, Rigidbody(
        mass=0.5, restitution=0.5, friction=0.3, use_gravity=True,
    ))
    world.add_component(box2, Collider(
        shape="aabb",
        size=np.array([0.6, 0.6, 0.6], dtype=np.float32),
    ))


    # ── Emisor de fuego ────────────────────────────────────────────────
    fire_eid = world.create_entity("Fuego")
    world.add_component(fire_eid, Transform(
        position=np.array([6.0, 0.0, 0.0], dtype=np.float32),
    ))
    fire_em = ParticleEmitter()
    apply_preset(os.path.join(_PARTICLES, "fire.json"), fire_em)
    world.add_component(fire_eid, fire_em)

    # ── Emisor de humo ─────────────────────────────────────────────────
    smoke_eid = world.create_entity("Humo")
    world.add_component(smoke_eid, Transform(
        position=np.array([8.0, 0.0, 0.0], dtype=np.float32),
    ))
    smoke_em = ParticleEmitter()
    apply_preset(os.path.join(_PARTICLES, "smoke.json"), smoke_em)
    world.add_component(smoke_eid, smoke_em)

    # ── Emisor de explosión ────────────────────────────────────────────
    expl_eid = world.create_entity("Explosion")
    world.add_component(expl_eid, Transform(
        position=np.array([4.0, 2.0, 4.0], dtype=np.float32),
    ))
    expl_em = ParticleEmitter()
    apply_preset(os.path.join(_PARTICLES, "explosion.json"), expl_em)
    world.add_component(expl_eid, expl_em)


def main():
    setup_opengl_format()
    app = QApplication(sys.argv)

    world = World()
    create_test_scene(world)

    window = MainWindow(world)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
