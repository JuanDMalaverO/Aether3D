"""
Aether3D — Punto de entrada.

Motor 3D con pipeline PBR, física, scripting y editor integrado.
Desarrollado íntegramente por Juan Malaver.
"""
import os
import sys
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QSurfaceFormat, QIcon

from engine.ecs import World
from engine.components import (
    Transform, MeshRenderer, Rigidbody, Collider,
    Script, ParticleEmitter, Material,
)
from engine.rendering import apply_preset
from editor.main_window import MainWindow
from editor.start_screen import StartScreen, record_opened_scene

_SCRIPTS   = os.path.join(os.path.dirname(__file__), "assets", "scripts")
_PARTICLES = os.path.join(os.path.dirname(__file__), "assets", "particles")


def setup_opengl_format():
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)


def create_default_scene(world: World):
    """Escena por defecto: física, partículas y jugador en primera persona.
    Desarrollada por Juan Malaver como escena de demostración del motor."""

    # ── Jugador (cápsula) ─────────────────────────────────────────────
    jugador = world.create_entity("Jugador")
    world.add_component(jugador, Transform(
        position=np.array([0.0, 1.1, 6.0], dtype=np.float32),
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
    world.add_component(jugador, Collider(shape="sphere", radius=0.38))

    # ── Suelo ─────────────────────────────────────────────────────────
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
        name="Suelo", albedo=np.array([0.35, 0.35, 0.40], np.float32),
        metallic=0.0, roughness=0.9,
    ))
    world.add_component(ground, Rigidbody(is_static=True, use_gravity=False))
    world.add_component(ground, Collider(
        shape="aabb", size=np.array([20.0, 0.5, 20.0], dtype=np.float32),
    ))

    # ── Plataforma ────────────────────────────────────────────────────
    plat = world.create_entity("Plataforma")
    world.add_component(plat, Transform(
        position=np.array([-4.0, 2.0, 0.0], dtype=np.float32),
        scale=np.array([3.0, 0.3, 3.0], dtype=np.float32),
    ))
    world.add_component(plat, MeshRenderer(
        mesh_name="cube", color=np.array([0.4, 0.3, 0.2], dtype=np.float32),
    ))
    world.add_component(plat, Material(
        name="Plataforma", albedo=np.array([0.4, 0.3, 0.2], np.float32),
        metallic=0.0, roughness=0.8,
    ))
    world.add_component(plat, Rigidbody(is_static=True, use_gravity=False))
    world.add_component(plat, Collider(
        shape="aabb", size=np.array([3.0, 0.3, 3.0], dtype=np.float32),
    ))

    # ── Pelota rebotadora ─────────────────────────────────────────────
    b1 = world.create_entity("PelotaRebotadora")
    world.add_component(b1, Transform(position=np.array([0.0, 6.0, 0.0], dtype=np.float32)))
    world.add_component(b1, MeshRenderer(mesh_name="sphere", color=np.array([0.9, 0.2, 0.2], dtype=np.float32)))
    world.add_component(b1, Material(name="PelotaRebotadora", albedo=np.array([0.9, 0.2, 0.2], np.float32), metallic=0.0, roughness=0.3))
    world.add_component(b1, Rigidbody(mass=1.0, restitution=0.85, friction=0.1, use_gravity=True))
    world.add_component(b1, Collider(shape="sphere", radius=0.5))
    world.add_component(b1, Script(path=os.path.join(_SCRIPTS, "jumper.py")))

    # ── Pelota cambia color ───────────────────────────────────────────
    b2 = world.create_entity("PelotaCambiante")
    world.add_component(b2, Transform(position=np.array([2.0, 8.0, 0.5], dtype=np.float32)))
    world.add_component(b2, MeshRenderer(mesh_name="sphere", color=np.array([0.2, 0.7, 0.3], dtype=np.float32)))
    world.add_component(b2, Material(name="PelotaCambiante", albedo=np.array([0.2, 0.7, 0.3], np.float32), metallic=0.0, roughness=0.4))
    world.add_component(b2, Rigidbody(mass=1.0, restitution=0.4, friction=0.4, use_gravity=True))
    world.add_component(b2, Collider(shape="sphere", radius=0.5))
    world.add_component(b2, Script(path=os.path.join(_SCRIPTS, "color_changer.py")))

    # ── Pelota pesada (metal) ─────────────────────────────────────────
    b3 = world.create_entity("PelotaPesada")
    world.add_component(b3, Transform(position=np.array([-2.0, 9.0, -0.5], dtype=np.float32)))
    world.add_component(b3, MeshRenderer(mesh_name="sphere", color=np.array([0.7, 0.5, 0.1], dtype=np.float32)))
    world.add_component(b3, Material(name="PelotaPesada", albedo=np.array([0.7, 0.5, 0.1], np.float32), metallic=0.8, roughness=0.2))
    world.add_component(b3, Rigidbody(mass=5.0, restitution=0.2, friction=0.6, use_gravity=True))
    world.add_component(b3, Collider(shape="sphere", radius=0.5))

    # ── Caja giratoria ────────────────────────────────────────────────
    box1 = world.create_entity("CajaGiratoria")
    world.add_component(box1, Transform(position=np.array([3.5, 5.0, 1.0], dtype=np.float32)))
    world.add_component(box1, MeshRenderer(mesh_name="cube", color=np.array([0.3, 0.5, 0.9], dtype=np.float32)))
    world.add_component(box1, Material(name="CajaGiratoria", albedo=np.array([0.3, 0.5, 0.9], np.float32), metallic=0.1, roughness=0.5))
    world.add_component(box1, Rigidbody(mass=2.0, restitution=0.3, friction=0.5, use_gravity=True))
    world.add_component(box1, Collider(shape="aabb", size=np.array([1.0, 1.0, 1.0], dtype=np.float32)))
    world.add_component(box1, Script(path=os.path.join(_SCRIPTS, "rotate.py")))

    # ── Caja pequeña ──────────────────────────────────────────────────
    box2 = world.create_entity("CajaPequeña")
    world.add_component(box2, Transform(position=np.array([-4.0, 3.5, 0.0], dtype=np.float32)))
    world.add_component(box2, MeshRenderer(mesh_name="cube", color=np.array([0.8, 0.4, 0.8], dtype=np.float32)))
    world.add_component(box2, Material(name="CajaPequeña", albedo=np.array([0.8, 0.4, 0.8], np.float32), metallic=0.0, roughness=0.4))
    world.add_component(box2, Rigidbody(mass=0.5, restitution=0.5, friction=0.3, use_gravity=True))
    world.add_component(box2, Collider(shape="aabb", size=np.array([0.6, 0.6, 0.6], dtype=np.float32)))

    # ── Partículas ────────────────────────────────────────────────────
    for name, pos, preset in [
        ("Fuego",     [6.0, 0.0, 0.0], "fire.json"),
        ("Humo",      [8.0, 0.0, 0.0], "smoke.json"),
        ("Explosion", [4.0, 2.0, 4.0], "explosion.json"),
    ]:
        eid = world.create_entity(name)
        world.add_component(eid, Transform(position=np.array(pos, dtype=np.float32)))
        em = ParticleEmitter()
        apply_preset(os.path.join(_PARTICLES, preset), em)
        world.add_component(eid, em)


def _open_editor(world: World, scene_path: str | None = None) -> MainWindow:
    """Crea y devuelve la ventana del editor con el mundo dado."""
    window = MainWindow(world)
    if scene_path:
        window._on_open_scene_path(scene_path)
    window.show()
    return window


def main():
    setup_opengl_format()
    app = QApplication(sys.argv)
    app.setApplicationName("Aether3D")
    app.setOrganizationName("Juan Malaver")

    # Referencia al editor (evita GC)
    _editor_ref = []

    def launch_editor(world: World, scene_path: str | None = None):
        win = _open_editor(world, scene_path)
        _editor_ref.append(win)

    # ── Pantalla de inicio ─────────────────────────────────────────────
    splash = StartScreen()

    def on_new_world():
        w = World()
        create_default_scene(w)
        launch_editor(w)

    def on_load_scene(path: str):
        w = World()
        launch_editor(w, scene_path=path)

    splash.new_world_requested.connect(on_new_world)
    splash.load_scene_requested.connect(on_load_scene)
    splash.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
