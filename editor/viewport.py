"""
Viewport - QOpenGLWidget embebido en la ventana del editor.
Inicializa el contexto OpenGL, carga shaders, y dispara el loop de render.
"""
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QTimer, Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QSurfaceFormat, QMouseEvent, QWheelEvent, QCursor
from PyQt6.QtWidgets import QMenu, QApplication, QLabel
from OpenGL.GL import *
import copy
import numpy as np
import pyrr
import ctypes
import os
import time

from engine.ecs import World
from engine.components import Transform, MeshRenderer, Rigidbody, Collider, ParticleEmitter, Camera, Material
from engine.rendering import Shader, create_cube, create_sphere, create_plane, create_capsule, OrbitCamera, Skybox, ShadowMap, PostProcess, ParticleSystem, IBL, MaterialRegistry
from engine.systems import RenderSystem, PhysicsSystem, ScriptSystem
from engine.gizmo import Gizmo, GizmoMode, GizmoAxis
from engine.input import Input


SHADER_DIR = os.path.join(os.path.dirname(__file__), "..", "shaders")


class Viewport(QOpenGLWidget):
    entity_picked          = pyqtSignal(object)   # int | None
    delete_entity_requested = pyqtSignal(int)    # pedido de borrado desde el viewport

    def __init__(self, world: World, parent=None):
        super().__init__(parent)
        self.world = world
        self.camera = OrbitCamera()
        self._last_mouse_pos: QPoint | None = None
        self._mmb_pressed = False
        self._shift_held = False
        self._last_time = time.perf_counter()
        self._left_press_pos: QPoint | None = None
        self._gizmo_dragging = False
        self._hovered_axis   = GizmoAxis.NONE
        self._keys_pressed: set  = set()
        self._camera_speed: float = 1.0

        # ── Estado del modo juego ─────────────────────────────────────
        self._game_state: str  = "stopped"   # "stopped" | "playing" | "paused"
        self._snapshot         = None

        # ── Cámara FPS ────────────────────────────────────────────────
        self._fps_mode: bool   = False
        self._fps_pos          = np.array([0.0, 1.7, 5.0], np.float32)
        self._fps_yaw: float   = 180.0   # mirando hacia -Z (origen)
        self._fps_pitch: float = 0.0
        self._mouse_captured: bool = False

        self.mesh_registry: dict = {}
        self.mesh_sources: dict = {}

        # ── Sistema de cámaras ────────────────────────────────────────
        # eid de la cámara a previsualizar en editor (None = cámara orbital)
        self._preview_camera_eid: int | None = None
        # eid de la cámara activa en play (None = modo FPS legacy)
        self._play_camera_eid:    int | None = None

        # Gizmo — inicializado en initializeGL (requiere contexto OpenGL)
        self.gizmo: Gizmo | None = None
        self.gizmo_mode: GizmoMode = GizmoMode.SELECT   # Select es el modo por defecto

        # Skybox activo (clave de string) y catálogo cargado en initializeGL
        self.active_skybox: str | None = "space"
        self._skyboxes: dict = {}

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

    # ---------- Lifecycle OpenGL ----------
    def initializeGL(self) -> None:
        glClearColor(0.15, 0.15, 0.17, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Cargar shaders
        self.basic_shader = Shader.from_files(
            os.path.join(SHADER_DIR, "basic.vert"),
            os.path.join(SHADER_DIR, "basic.frag"),
        )
        self.grid_shader = Shader.from_files(
            os.path.join(SHADER_DIR, "grid.vert"),
            os.path.join(SHADER_DIR, "grid.frag"),
        )
        self.outline_shader = Shader.from_files(
            os.path.join(SHADER_DIR, "outline.vert"),
            os.path.join(SHADER_DIR, "outline.frag"),
        )

        # Primitivas built-in
        self.mesh_registry.update({
            "cube":    create_cube(),
            "sphere":  create_sphere(),
            "plane":   create_plane(),
            "capsule": create_capsule(),
        })

        # Sistema de render
        self.render_system = RenderSystem(self.world, self.basic_shader, self.mesh_registry)

        # Gizmo
        self.flat_shader = Shader.from_files(
            os.path.join(SHADER_DIR, "flat.vert"),
            os.path.join(SHADER_DIR, "flat.frag"),
        )
        self.gizmo = Gizmo()

        # Shadow map
        self.depth_shader = Shader.from_files(
            os.path.join(SHADER_DIR, "depth.vert"),
            os.path.join(SHADER_DIR, "depth.frag"),
        )
        self.shadow_map = ShadowMap()

        # Quad del grid (2 triángulos en NDC)
        self._setup_grid_quad()

        # Shader del skybox
        self.skybox_shader = Shader.from_files(
            os.path.join(SHADER_DIR, "skybox.vert"),
            os.path.join(SHADER_DIR, "skybox.frag"),
        )

        # Cargar skyboxes desde assets/skyboxes/{name}/
        _sb_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "skyboxes"))
        for _name in ("space", "sky"):
            _face_dir = os.path.join(_sb_root, _name)
            if os.path.isdir(_face_dir):
                try:
                    self._skyboxes[_name] = Skybox(_face_dir)
                except Exception as _e:
                    print(f"[Skybox] '{_name}' no se pudo cargar: {_e}")

        # PBR: shader, IBL y MaterialRegistry
        self.pbr_shader = None
        try:
            self.pbr_shader = Shader.from_files(
                os.path.join(SHADER_DIR, "pbr.vert"),
                os.path.join(SHADER_DIR, "pbr.frag"),
            )
        except Exception as _e:
            print(f"[PBR] No se pudo cargar pbr shader: {_e}")

        self.ibl = IBL()
        self.material_registry = MaterialRegistry()

        # Cargar materiales predefinidos desde assets/materials/
        _mat_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "materials"))
        self.material_registry.load_dir(_mat_dir)

        # Inyectar en el render system
        self.render_system.pbr_shader       = self.pbr_shader
        self.render_system.ibl              = self.ibl
        self.render_system.material_registry = self.material_registry

        # Computar IBL diferido para no bloquear el arranque
        from PyQt6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(500, self._compute_ibl_for_active_skybox)

        # Post-procesado (FBO offscreen + efectos fullscreen)
        self.post_shader = Shader.from_files(
            os.path.join(SHADER_DIR, "post.vert"),
            os.path.join(SHADER_DIR, "post.frag"),
        )
        self.post_process = PostProcess(
            max(1, self.width()), max(1, self.height()), self.post_shader
        )

        # Sistema de física
        self.physics_system = PhysicsSystem(self.world)
        self.physics_enabled = True

        # Sistema de partículas
        self.particle_shader = Shader.from_files(
            os.path.join(SHADER_DIR, "particles.vert"),
            os.path.join(SHADER_DIR, "particles.frag"),
        )
        self.particle_system = ParticleSystem(self.world, self.particle_shader)

        # Sistema de scripting
        self.play_mode = False
        self.script_system = ScriptSystem(self.world)
        self.physics_system.collision_listeners.append(
            self.script_system.notify_collision
        )

        # VAO para el borde indicador de modo juego (NDC quads)
        self._border_vao = glGenVertexArrays(1)
        self._border_vbo = glGenBuffers(1)
        glBindVertexArray(self._border_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._border_vbo)
        glBufferData(GL_ARRAY_BUFFER, 24 * 3 * 4, None, GL_DYNAMIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

        # QLabel de indicador de estado (overlay Qt sobre OpenGL)
        self._state_label = QLabel(self)
        self._state_label.setStyleSheet(
            "QLabel { color: #fff; background: rgba(0,0,0,160);"
            "  padding: 4px 10px; border: none;"
            "  font-size: 12px; font-weight: bold; }"
        )
        self._state_label.hide()

        # Wireframes para visualizar colliders (reusan flat_shader)
        self._wire_box_vao,    self._wire_box_count    = self._make_wire_box()
        self._wire_sphere_vao, self._wire_sphere_count = self._make_wire_sphere()

        # VAO/VBO dinámico para los frustums de cámaras (máx 64 líneas = 128 verts × 3 floats)
        self._cam_frust_vao = glGenVertexArrays(1)
        self._cam_frust_vbo = glGenBuffers(1)
        glBindVertexArray(self._cam_frust_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._cam_frust_vbo)
        glBufferData(GL_ARRAY_BUFFER, 128 * 3 * 4, None, GL_DYNAMIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

    # ══════════════════════════════════════════════════════════════════════
    # ── Modo Juego: Play / Pause / Stop ───────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════

    def start_play(self) -> None:
        self._snapshot = self._take_snapshot()
        self._game_state = "playing"
        self.play_mode   = True

        # ¿Hay alguna entidad con Camera(is_main=True)?
        main = self._find_main_camera()
        if main is not None:
            self._play_camera_eid = main[0]
            self._fps_mode = False
        else:
            # Modo FPS legacy (sin entidad Camera)
            self._play_camera_eid = None
            self._fps_mode = True
            eid = self._find_player()
            if eid is not None:
                tr = self.world.get_component(eid, Transform)
                if tr is not None:
                    self._fps_pos = tr.position.astype(np.float32) + np.array([0, 0.8, 0], np.float32)
                mr = self.world.get_component(eid, MeshRenderer)
                if mr is not None:
                    mr.visible = False
            self._fps_yaw   = 180.0
            self._fps_pitch = 0.0

        Input._clear_mouse_delta()
        self._capture_mouse()
        self.script_system.start_play()
        self._update_state_label()
        self.update()

    def pause_play(self) -> None:
        if self._game_state == "playing":
            self._game_state = "paused"
            self.play_mode   = False
        elif self._game_state == "paused":
            self._game_state = "playing"
            self.play_mode   = True
        self._update_state_label()
        self.update()

    def stop_play(self) -> None:
        self._release_mouse()
        Input._clear_mouse_delta()
        self.script_system.stop_play()
        self.particle_system.stop_all()
        if self._snapshot is not None:
            self._restore_snapshot(self._snapshot)
            self._snapshot = None
        self._game_state      = "stopped"
        self.play_mode        = False
        self._fps_mode        = False
        self._play_camera_eid = None
        self._update_state_label()
        self.update()

    def _find_player(self) -> int | None:
        for eid in self.world.all_entities():
            n = self.world.get_entity_name(eid)
            if "Jugador" in n or "Player" in n:
                return eid
        return None

    def _find_main_camera(self):
        """Devuelve (eid, Camera, Transform) de la cámara principal, o None."""
        for eid in self.world.all_entities():
            cam = self.world.get_component(eid, Camera)
            if cam is not None and cam.is_main:
                tr = self.world.get_component(eid, Transform)
                if tr is not None:
                    return (eid, cam, tr)
        return None

    def _get_cam_view_proj(self, eid: int, cam: Camera, aspect: float):
        """Construye matrices view/proj desde el Transform y Camera de una entidad."""
        tr = self.world.get_component(eid, Transform)
        if tr is None:
            return self.camera.view_matrix(), self.camera.projection_matrix(aspect)

        wm  = tr.world_matrix(self.world)
        pos = wm[3, :3].astype(np.float32)

        # Extraer ejes locales (columnas en column-major = filas en row-major)
        right_v = wm[0, :3].astype(np.float32)
        up_v    = wm[1, :3].astype(np.float32)
        back_v  = wm[2, :3].astype(np.float32)
        for v in (right_v, up_v, back_v):
            n = np.linalg.norm(v)
            if n > 1e-8:
                v /= n

        fwd  = -back_v   # la cámara mira en -Z local
        view = pyrr.matrix44.create_look_at(pos, pos + fwd, up_v, dtype=np.float32)

        if cam.projection == "orthographic":
            h    = cam.ortho_size * 0.5
            w    = h * aspect
            proj = self._make_ortho_proj(-w, w, -h, h, cam.near, cam.far)
        else:
            proj = pyrr.matrix44.create_perspective_projection(
                cam.fov, aspect, cam.near, cam.far, dtype=np.float32)

        return view, proj

    @staticmethod
    def _make_ortho_proj(l, r, b, t, n, f) -> np.ndarray:
        """Matriz ortográfica row-major compatible con pyrr (traslación en fila 3)."""
        m = np.zeros((4, 4), dtype=np.float32)
        m[0, 0] =  2 / (r - l)
        m[1, 1] =  2 / (t - b)
        m[2, 2] = -2 / (f - n)
        m[3, 0] = -(r + l) / (r - l)
        m[3, 1] = -(t + b) / (t - b)
        m[3, 2] = -(f + n) / (f - n)
        m[3, 3] = 1.0
        return m

    def _take_snapshot(self) -> dict:
        return {
            'components': copy.deepcopy(dict(self.world._components)),
            'entities':   copy.deepcopy(self.world._entities),
            'names':      copy.deepcopy(self.world._entity_names),
            'next_id':    self.world._next_entity_id,
            'selected':   self.world.selected_entity,
        }

    def _restore_snapshot(self, snap: dict) -> None:
        self.world._components.clear()
        for ct, cd in copy.deepcopy(snap['components']).items():
            self.world._components[ct].update(cd)
        self.world._entities        = copy.deepcopy(snap['entities'])
        self.world._entity_names    = copy.deepcopy(snap['names'])
        self.world._next_entity_id  = snap['next_id']
        self.world.selected_entity  = snap['selected']

    # ── Cámara FPS ────────────────────────────────────────────────────────
    def _fps_view(self) -> np.ndarray:
        yr = np.radians(self._fps_yaw)
        pr = np.radians(self._fps_pitch)
        fwd = np.array([np.cos(pr) * np.sin(yr),
                        np.sin(pr),
                        np.cos(pr) * np.cos(yr)], np.float32)
        eye = self._fps_pos
        up  = np.array([0, 1, 0], np.float32)
        right = np.cross(fwd, up)
        rn    = np.linalg.norm(right)
        right = right / rn if rn > 1e-8 else np.array([1, 0, 0], np.float32)
        actual_up = np.cross(right, fwd)
        return pyrr.matrix44.create_look_at(eye, eye + fwd, actual_up, dtype=np.float32)

    def _handle_fps_movement(self, dt: float) -> None:
        """Aplica velocidad al Rigidbody del jugador con WASD."""
        eid = self._find_player()
        if eid is None:
            return
        tr = self.world.get_component(eid, Transform)
        rb = self.world.get_component(eid, Rigidbody)
        if tr is None or rb is None:
            return

        # Ojo en la parte alta de la cápsula (0.8 sobre el centro del Transform)
        # La cápsula tiene radio=0.35 + cilindro=1.5 → total=2.2 → top a 1.1 sobre centro
        # 0.8 coloca el ojo cerca del cuello, fuera del mesh
        self._fps_pos = tr.position.astype(np.float32) + np.array([0, 0.8, 0], np.float32)

        yr  = np.radians(self._fps_yaw)
        fwd   = np.array([ np.sin(yr), 0,  np.cos(yr)], np.float32)
        # right = cross(fwd, world_up) = (-cos(yr), 0, sin(yr))
        right = np.array([-np.cos(yr), 0,  np.sin(yr)], np.float32)

        spd = 5.0 * self._camera_speed
        K = Qt.Key
        vx = vz = 0.0
        if K.Key_W in self._keys_pressed: vx += fwd[0]*spd;   vz += fwd[2]*spd
        if K.Key_S in self._keys_pressed: vx -= fwd[0]*spd;   vz -= fwd[2]*spd
        if K.Key_D in self._keys_pressed: vx += right[0]*spd; vz += right[2]*spd
        if K.Key_A in self._keys_pressed: vx -= right[0]*spd; vz -= right[2]*spd

        rb.velocity[0] = vx
        rb.velocity[2] = vz

        # Salto con Espacio (si prácticamente en reposo vertical)
        if (Qt.Key.Key_Space in self._keys_pressed
                and abs(float(rb.velocity[1])) < 0.8):
            rb.velocity[1] = 7.0

    def _capture_mouse(self) -> None:
        # Limpiar overrides previos para no apilar cursores
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
        self._mouse_captured = True
        self.setMouseTracking(True)
        self.setFocus()
        self._center_cursor()

    def _release_mouse(self) -> None:
        if self._mouse_captured:
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            self._mouse_captured = False

    def _center_cursor(self) -> None:
        center = self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2))
        QCursor.setPos(center)

    def _ensure_mouse_captured(self) -> None:
        """Llamado cada frame en play: garantiza que el cursor está siempre capturado."""
        if QApplication.overrideCursor() is None:
            # El override se perdió (p. ej. por Alt+Tab) → reaplicarlo
            QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
        self._center_cursor()

    def focusInEvent(self, event) -> None:
        """Al recuperar el foco, volver a capturar el mouse si estamos jugando."""
        super().focusInEvent(event)
        if self._game_state == "playing":
            self._capture_mouse()

    def _handle_fps_mouse(self, event: QMouseEvent) -> None:
        center = self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2))
        gp = event.globalPosition()
        dx = gp.x() - center.x()
        dy = gp.y() - center.y()
        if abs(dx) > 0.5 or abs(dy) > 0.5:
            # Alimentar Input para scripts (first_person_controller, third_person_controller)
            Input._set_mouse_delta(float(dx), float(dy))
            # Modo FPS legacy: rotar cámara directamente
            if self._play_camera_eid is None:
                self._fps_yaw   -= dx * 0.12
                self._fps_pitch  = max(-89.0, min(89.0, self._fps_pitch - dy * 0.12))
            QCursor.setPos(center)
        else:
            Input._set_mouse_delta(0.0, 0.0)

    # ── Borde indicador ───────────────────────────────────────────────────
    def _draw_play_border(self) -> None:
        if self._game_state == "playing":
            color = np.array([0.85, 0.10, 0.10], np.float32)
        else:
            color = np.array([0.85, 0.78, 0.02], np.float32)

        t = 0.014  # grosor en NDC
        verts = np.array([
            # Top
            -1,1-t,0,  1,1-t,0,  1,1,0,   -1,1-t,0,  1,1,0,  -1,1,0,
            # Bottom
            -1,-1,0,   1,-1,0,   1,-1+t,0, -1,-1,0,   1,-1+t,0, -1,-1+t,0,
            # Left
            -1,-1+t,0, -1+t,-1+t,0, -1+t,1-t,0, -1,-1+t,0, -1+t,1-t,0, -1,1-t,0,
            # Right
            1-t,-1+t,0, 1,-1+t,0, 1,1-t,0, 1-t,-1+t,0, 1,1-t,0, 1-t,1-t,0,
        ], dtype=np.float32)

        glDisable(GL_DEPTH_TEST)
        self.flat_shader.use()
        self.flat_shader.set_mat4("uModel",      np.eye(4, dtype=np.float32))
        self.flat_shader.set_mat4("uView",       np.eye(4, dtype=np.float32))
        self.flat_shader.set_mat4("uProjection", np.eye(4, dtype=np.float32))
        self.flat_shader.set_vec3("uColor", color)
        glBindBuffer(GL_ARRAY_BUFFER, self._border_vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_DYNAMIC_DRAW)
        glBindVertexArray(self._border_vao)
        glDrawArrays(GL_TRIANGLES, 0, 24)
        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

    # ── Mini preview de la cámara principal ──────────────────────────────
    def _draw_mini_preview(self) -> None:
        """Renderiza un thumbnail 240×135 de la cámara principal en la esquina inferior derecha."""
        main = self._find_main_camera()
        if main is None:
            return
        eid, cam, _ = main

        W, H  = self.width(), self.height()
        pw, ph = 240, 135
        # GL coords: origen en esquina inferior-izquierda
        px = W - pw - 8
        py = 8

        # Guardar estado previo
        aspect = pw / max(1, ph)
        view_p, proj_p = self._get_cam_view_proj(eid, cam, aspect)
        wm     = self.world.get_component(eid, Transform).world_matrix(self.world)
        cpos_p = wm[3, :3].astype(np.float32)

        # Fondo oscuro + render de escena en viewport recortado
        glEnable(GL_SCISSOR_TEST)
        glScissor(px, py, pw, ph)
        glViewport(px, py, pw, ph)
        glClearColor(0.08, 0.08, 0.10, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glClearColor(0.15, 0.15, 0.17, 1.0)   # restaurar color de clear principal

        old_view = self.render_system.view
        old_proj = self.render_system.projection
        old_cpos = self.render_system.camera_pos

        self.render_system.view       = view_p
        self.render_system.projection = proj_p
        self.render_system.camera_pos = cpos_p
        self.render_system.update(0)

        self.render_system.view       = old_view
        self.render_system.projection = old_proj
        self.render_system.camera_pos = old_cpos

        # Skybox en el preview
        skybox = self._skyboxes.get(self.active_skybox)
        if skybox:
            skybox.draw(self.skybox_shader, view_p, proj_p)

        glDisable(GL_SCISSOR_TEST)
        glViewport(0, 0, W, H)

        # Borde blanco alrededor del preview usando el flat_shader en NDC local
        # Convertimos el rect de píxeles a NDC del viewport principal
        def _px_to_ndc_x(x): return x / W * 2 - 1
        def _px_to_ndc_y(y): return y / H * 2 - 1

        x0 = _px_to_ndc_x(px - 1)
        x1 = _px_to_ndc_x(px + pw + 1)
        y0 = _px_to_ndc_y(py - 1)
        y1 = _px_to_ndc_y(py + ph + 1)
        bw = 2.0 / W  # 1 px en NDC

        border_verts = np.array([
            x0, y1-bw, 0,  x1, y1-bw, 0,  x1, y1, 0,   x0, y1-bw, 0,  x1, y1, 0,  x0, y1, 0,
            x0, y0, 0,     x1, y0, 0,     x1, y0+bw, 0, x0, y0, 0,     x1, y0+bw, 0, x0, y0+bw, 0,
            x0, y0+bw, 0,  x0+bw, y0+bw, 0, x0+bw, y1-bw, 0, x0, y0+bw, 0, x0+bw, y1-bw, 0, x0, y1-bw, 0,
            x1-bw, y0+bw, 0, x1, y0+bw, 0, x1, y1-bw, 0, x1-bw, y0+bw, 0, x1, y1-bw, 0, x1-bw, y1-bw, 0,
        ], dtype=np.float32)

        glDisable(GL_DEPTH_TEST)
        self.flat_shader.use()
        self.flat_shader.set_mat4("uModel",      np.eye(4, dtype=np.float32))
        self.flat_shader.set_mat4("uView",       np.eye(4, dtype=np.float32))
        self.flat_shader.set_mat4("uProjection", np.eye(4, dtype=np.float32))
        self.flat_shader.set_vec3("uColor", np.array([0.8, 0.8, 0.9], np.float32))
        glBindBuffer(GL_ARRAY_BUFFER, self._border_vbo)
        glBufferData(GL_ARRAY_BUFFER, border_verts.nbytes, border_verts, GL_DYNAMIC_DRAW)
        glBindVertexArray(self._border_vao)
        glDrawArrays(GL_TRIANGLES, 0, 24)
        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

        # Etiqueta "CAM" superpuesta como QLabel (se posiciona en coordenadas Qt)
        if not hasattr(self, '_preview_label'):
            self._preview_label = QLabel("CAM", self)
            self._preview_label.setStyleSheet(
                "QLabel{color:#fff;background:rgba(0,0,0,140);"
                "padding:1px 5px;border:none;font-size:10px;font-weight:bold;}")
        self._preview_label.adjustSize()
        # Qt Y=0 está arriba; GL py=8 desde abajo → Qt y = H - (py + ph)
        self._preview_label.move(px + 4, H - (py + ph) + 4)
        self._preview_label.show()

    def _hide_mini_preview_label(self) -> None:
        if hasattr(self, '_preview_label'):
            self._preview_label.hide()

    def _update_state_label(self) -> None:
        if self._game_state == "playing":
            self._state_label.setText("▶  REPRODUCIENDO  —  WASD mover  ·  Mouse girar  ·  Espacio saltar  ·  Esc detener")
            self._state_label.setStyleSheet(
                "QLabel{color:#fff;background:rgba(180,30,30,200);"
                "padding:4px 10px;border:none;font-size:12px;font-weight:bold;}")
            self._state_label.adjustSize()
            self._state_label.move(10, 10)
            self._state_label.show()
        elif self._game_state == "paused":
            self._state_label.setText("⏸  PAUSA")
            self._state_label.setStyleSheet(
                "QLabel{color:#fff;background:rgba(160,140,0,200);"
                "padding:4px 10px;border:none;font-size:12px;font-weight:bold;}")
            self._state_label.adjustSize()
            self._state_label.move(10, 10)
            self._state_label.show()
        else:
            self._state_label.hide()

        # Ocultar preview label cuando no está en modo editor
        if self._game_state != "stopped":
            self._hide_mini_preview_label()

    # ── Geometría wireframe de colliders ──────────────────────────────────
    def _make_wire_box(self):
        """Cubo unitario [-1,1]^3, 12 aristas → 24 vértices GL_LINES."""
        c = np.array([
            [-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],  # cara inferior
            [-1,-1, 1],[1,-1, 1],[1,1, 1],[-1,1, 1],  # cara superior
        ], dtype=np.float32)
        idx = [0,1,1,2,2,3,3,0,  4,5,5,6,6,7,7,4,  0,4,1,5,2,6,3,7]
        verts = c[idx].flatten()
        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)
        return vao, len(idx)

    def _make_wire_sphere(self, N=32):
        """3 anillos de N segmentos cada uno (planos XY, YZ, XZ)."""
        verts = []
        for plane in range(3):
            for i in range(N):
                a1, a2 = 2*np.pi*i/N, 2*np.pi*(i+1)/N
                c1, s1, c2, s2 = np.cos(a1), np.sin(a1), np.cos(a2), np.sin(a2)
                if plane == 0: verts += [c1, s1, 0, c2, s2, 0]
                elif plane == 1: verts += [0, c1, s1, 0, c2, s2]
                else:            verts += [c1, 0, s1, c2, 0, s2]
        verts = np.array(verts, dtype=np.float32)
        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)
        return vao, N * 3 * 2

    def _draw_camera_frustums(self, view, proj) -> None:
        """Dibuja el ícono y frustum corto de cada entidad con Camera en el editor."""
        NEAR = 0.25   # plano próximo del frustum visual
        FAR  = 2.0    # plano lejano del frustum visual (corto, solo orientativo)
        ASPECT = 16.0 / 9.0

        selected_eid = self.world.selected_entity

        glDisable(GL_DEPTH_TEST)
        self.flat_shader.use()
        self.flat_shader.set_mat4("uView",       view)
        self.flat_shader.set_mat4("uProjection", proj)
        self.flat_shader.set_mat4("uModel",      np.eye(4, dtype=np.float32))

        for eid in self.world.all_entities():
            cam = self.world.get_component(eid, Camera)
            if cam is None:
                continue
            tr = self.world.get_component(eid, Transform)
            if tr is None:
                continue

            wm = tr.world_matrix(self.world)
            pos = wm[3, :3].astype(np.float32)

            # Ejes locales normalizados de la cámara
            right_v = wm[0, :3].astype(np.float32)
            up_v    = wm[1, :3].astype(np.float32)
            back_v  = wm[2, :3].astype(np.float32)
            for v in (right_v, up_v, back_v):
                n = np.linalg.norm(v)
                if n > 1e-8:
                    v /= n
            fwd = -back_v

            # Semidimensiones de los planos near/far del frustum visual
            if cam.projection == "orthographic":
                hw_n = hw_f = cam.ortho_size * ASPECT * 0.5
                hh_n = hh_f = cam.ortho_size * 0.5
            else:
                tan_h = np.tan(np.radians(cam.fov * 0.5))
                hh_n  = NEAR * tan_h;  hw_n = hh_n * ASPECT
                hh_f  = FAR  * tan_h;  hw_f = hh_f * ASPECT

            # Centros de los planos
            nc = pos + fwd * NEAR
            fc = pos + fwd * FAR

            # 4 esquinas de cada plano (orden: TR, TL, BL, BR)
            def _corners(center, hw, hh):
                r, u = right_v, up_v
                return [
                    center + r*hw + u*hh,
                    center - r*hw + u*hh,
                    center - r*hw - u*hh,
                    center + r*hw - u*hh,
                ]
            nc4 = _corners(nc, hw_n, hh_n)
            fc4 = _corners(fc, hw_f, hh_f)

            # Construcción del buffer de líneas
            lines = []
            # Rectángulo near
            for i in range(4):
                lines += list(nc4[i]); lines += list(nc4[(i+1) % 4])
            # Rectángulo far
            for i in range(4):
                lines += list(fc4[i]); lines += list(fc4[(i+1) % 4])
            # Conectoras near→far
            for i in range(4):
                lines += list(nc4[i]); lines += list(fc4[i])
            # Líneas desde el apex (solo perspectiva, da el efecto de pirámide)
            if cam.projection != "orthographic":
                for c in nc4:
                    lines += list(pos); lines += list(c)

            # ── Icono de cuerpo de cámara (caja pequeña detrás del apex) ──
            # Un pequeño rectángulo que representa el "cuerpo" de la cámara
            body_d = 0.15   # semiprofundidad del cuerpo
            body_h = 0.10
            body_w = 0.14
            body_f = pos - fwd * body_d   # frente del cuerpo = apex de la cámara
            body_b = pos - fwd * (body_d + body_d * 2)  # trasero

            def _box_corners(center, fw, fh):
                return [
                    center + right_v*fw + up_v*fh,
                    center - right_v*fw + up_v*fh,
                    center - right_v*fw - up_v*fh,
                    center + right_v*fw - up_v*fh,
                ]
            bf4 = _box_corners(body_f, body_w, body_h)
            bb4 = _box_corners(body_b, body_w, body_h)
            for i in range(4):
                lines += list(bf4[i]); lines += list(bf4[(i+1) % 4])
                lines += list(bb4[i]); lines += list(bb4[(i+1) % 4])
                lines += list(bf4[i]); lines += list(bb4[i])

            verts = np.array(lines, dtype=np.float32)

            # Color: amarillo dorado si es la principal/seleccionada, cian si no
            if eid == selected_eid:
                color = np.array([1.0, 0.6, 0.05], np.float32)
            elif cam.is_main:
                color = np.array([1.0, 0.85, 0.15], np.float32)
            else:
                color = np.array([0.25, 0.75, 1.0], np.float32)

            self.flat_shader.set_vec3("uColor", color)
            glBindBuffer(GL_ARRAY_BUFFER, self._cam_frust_vbo)
            glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_DYNAMIC_DRAW)
            glBindVertexArray(self._cam_frust_vao)
            glDrawArrays(GL_LINES, 0, len(verts) // 3)
            glBindVertexArray(0)

        glEnable(GL_DEPTH_TEST)

    def _draw_collider_wireframe(self, view, proj) -> None:
        """Dibuja el wireframe verde del collider de la entidad seleccionada."""
        eid = self.world.selected_entity
        if eid is None:
            return
        collider  = self.world.get_component(eid, Collider)
        if collider is None:
            return
        transform = self.world.get_component(eid, Transform)
        if transform is None:
            return

        wm        = transform.world_matrix(self.world)
        world_pos = wm[3, :3].astype(np.float32)
        sx = float(np.linalg.norm(wm[0, :3]))
        sy = float(np.linalg.norm(wm[1, :3]))
        sz = float(np.linalg.norm(wm[2, :3]))
        center = world_pos + collider.offset.astype(np.float32)

        # Construir model matrix (escala + traslación, sin rotación)
        def _model(scale_xyz):
            M = np.eye(4, dtype=np.float32)
            M[0, 0], M[1, 1], M[2, 2] = scale_xyz
            M[3, :3] = center
            return M

        glDisable(GL_DEPTH_TEST)
        self.flat_shader.use()
        self.flat_shader.set_mat4("uView", view)
        self.flat_shader.set_mat4("uProjection", proj)
        self.flat_shader.set_vec3("uColor", np.array([0.15, 0.95, 0.25], np.float32))

        if collider.shape == "aabb":
            half = collider.size * 0.5 * np.array([sx, sy, sz], np.float32)
            self.flat_shader.set_mat4("uModel", _model(half))
            glBindVertexArray(self._wire_box_vao)
            glDrawArrays(GL_LINES, 0, self._wire_box_count)
        else:
            r = float(collider.radius) * max(sx, sy, sz)
            self.flat_shader.set_mat4("uModel", _model([r, r, r]))
            glBindVertexArray(self._wire_sphere_vao)
            glDrawArrays(GL_LINES, 0, self._wire_sphere_count)

        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

    def _setup_grid_quad(self) -> None:
        verts = np.array([
            -1, -1, 0,
             1, -1, 0,
             1,  1, 0,
            -1, -1, 0,
             1,  1, 0,
            -1,  1, 0,
        ], dtype=np.float32)
        self.grid_vao = glGenVertexArrays(1)
        self.grid_vbo = glGenBuffers(1)
        glBindVertexArray(self.grid_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.grid_vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

    def resizeGL(self, w: int, h: int) -> None:
        glViewport(0, 0, w, h)
        if hasattr(self, 'post_process'):
            self.post_process.resize(w, h)

    def paintGL(self) -> None:
        now = time.perf_counter()
        dt  = now - self._last_time
        self._last_time = now

        # Mantener captura del mouse en todo momento mientras se juega
        if self._game_state == "playing":
            self._ensure_mouse_captured()

        aspect = self.width() / max(1, self.height())

        # Actualizar Input con teclas actuales (solo en play)
        if self._game_state == "playing":
            Input._set_keys(self._keys_pressed)

        # Selección de vista y movimiento según estado
        if self._game_state == "playing":
            if self._play_camera_eid is not None:
                # Cámara dirigida por script: solo leer el Transform actual
                cam_comp = self.world.get_component(self._play_camera_eid, Camera)
                if cam_comp is not None:
                    view, proj = self._get_cam_view_proj(self._play_camera_eid, cam_comp, aspect)
                    _cam_pos = self.world.get_component(self._play_camera_eid, Transform)
                    cam_pos = _cam_pos.world_matrix(self.world)[3,:3] if _cam_pos else self.camera.position
                else:
                    view = self._fps_view()
                    proj = self.camera.projection_matrix(aspect)
                    cam_pos = self._fps_pos
            else:
                # Modo FPS legacy
                self._handle_fps_movement(dt)
                view = self._fps_view()
                proj = self.camera.projection_matrix(aspect)
                cam_pos = self._fps_pos
        else:
            if self._game_state == "stopped":
                self._handle_wasd(dt)
            if self._preview_camera_eid is not None:
                cam_comp = self.world.get_component(self._preview_camera_eid, Camera)
                if cam_comp is not None:
                    view, proj = self._get_cam_view_proj(self._preview_camera_eid, cam_comp, aspect)
                    _ptr = self.world.get_component(self._preview_camera_eid, Transform)
                    cam_pos = _ptr.world_matrix(self.world)[3,:3] if _ptr else self.camera.position
                else:
                    view    = self.camera.view_matrix()
                    proj    = self.camera.projection_matrix(aspect)
                    cam_pos = self.camera.position
            elif self._fps_mode:
                view    = self._fps_view()
                proj    = self.camera.projection_matrix(aspect)
                cam_pos = self._fps_pos
            else:
                view    = self.camera.view_matrix()
                proj    = self.camera.projection_matrix(aspect)
                cam_pos = self.camera.position

        # ── Sistemas (solo activos cuando se está jugando, no en pausa) ─────
        _running = self._game_state == "playing"
        if _running and self.physics_enabled:
            self.physics_system.update(dt)
        if _running:
            self.particle_system.update(dt)
            self.script_system.update(dt)

        # ── Pasada de sombra (depth-only desde la luz) ────────────────────
        if self.shadow_map.enabled:
            self._do_shadow_pass()

        # ── Bind del FBO de post-procesado (si está activo) ───────────────
        pp = getattr(self, 'post_process', None)
        if pp and pp.enabled:
            pp.begin()

        # ── Viewport + clear de la pasada de color ────────────────────────
        glViewport(0, 0, self.width(), self.height())
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # ── Pasada de color ───────────────────────────────────────────────
        self.render_system.view       = view
        self.render_system.projection = proj
        self.render_system.camera_pos = cam_pos
        self.render_system.shadow_map = self.shadow_map
        self.render_system.update(dt)

        # Contorno de la entidad seleccionada
        self._draw_outline(view, proj)

        # Skybox: se dibuja DESPUÉS de la escena con depth GL_LEQUAL para
        # "rellenar" solo los píxeles donde no hay objeto (depth = 1.0).
        self._draw_skybox(view, proj)

        # Partículas: transparentes, después de los opacos, antes del gizmo
        if self.play_mode and hasattr(self, 'particle_system'):
            self.particle_system.draw(view, proj)

        # Gizmo encima de todo (sin depth test dentro del método)
        self._draw_gizmo(view, proj)

        # Grid encima de todo (transparente)
        self._draw_grid(view, proj)

        # Wireframe del collider de la entidad seleccionada
        self._draw_collider_wireframe(view, proj)

        # Frustums de cámaras (solo en modo editor)
        if self._game_state == "stopped":
            self._draw_camera_frustums(view, proj)

        # Borde de indicador de modo juego (sobre todo lo demás)
        if self._game_state != "stopped":
            self._draw_play_border()

        # ── Aplicar efectos de post-procesado y volcar a pantalla ─────────
        if pp and pp.enabled:
            pp.end()

        # ── Preview en miniatura de la cámara principal (solo modo editor) ──
        if self._game_state == "stopped":
            self._draw_mini_preview()

    def _do_shadow_pass(self) -> None:
        """Renderiza la escena desde el punto de vista de la luz (depth only)."""
        self.shadow_map.update_light_matrix(
            self.render_system.light_dir,
            np.zeros(3, np.float32),
            20.0,
        )
        self.shadow_map.begin_pass()

        self.depth_shader.use()
        lsm = self.shadow_map.light_space_matrix
        self.depth_shader.set_mat4("uLightSpaceMatrix", lsm)

        for eid, (transform, mr) in self.world.query(Transform, MeshRenderer):
            if not mr.visible:
                continue
            mesh = self.mesh_registry.get(mr.mesh_name)
            if mesh is None:
                continue
            self.depth_shader.set_mat4("uModel", transform.world_matrix(self.world))
            mesh.draw()

        self.shadow_map.end_pass()

    def _draw_outline(self, view, proj) -> None:
        entity_id = self.world.selected_entity
        if entity_id is None:
            return
        transform = self.world.get_component(entity_id, Transform)
        mesh_renderer = self.world.get_component(entity_id, MeshRenderer)
        if transform is None or mesh_renderer is None or not mesh_renderer.visible:
            return
        mesh = self.mesh_registry.get(mesh_renderer.mesh_name)
        if mesh is None:
            return

        # Dibujamos el mesh inflado por sus normales con culling de caras frontales:
        # solo las caras traseras del mesh agrandado quedan visibles como contorno.
        glEnable(GL_CULL_FACE)
        glCullFace(GL_FRONT)

        self.outline_shader.use()
        self.outline_shader.set_mat4("uModel", transform.world_matrix(self.world))
        self.outline_shader.set_mat4("uView", view)
        self.outline_shader.set_mat4("uProjection", proj)
        self.outline_shader.set_float("uOutlineWidth", 0.04)
        self.outline_shader.set_vec3("uOutlineColor", np.array([1.0, 0.75, 0.0], dtype=np.float32))

        mesh.draw()

        glCullFace(GL_BACK)
        glDisable(GL_CULL_FACE)

    def _draw_gizmo(self, view, proj) -> None:
        if self.gizmo is None or self.gizmo_mode == GizmoMode.SELECT:
            return
        t = self._selected_transform()
        if t is None:
            return
        self.gizmo.draw(
            self.flat_shader, view, proj,
            t, self.world,
            self.camera.position, self.gizmo_mode, self._hovered_axis,
        )

    def set_gizmo_mode(self, mode) -> None:
        if isinstance(mode, str):
            mode = {
                "select":    GizmoMode.SELECT,
                "translate": GizmoMode.TRANSLATE,
                "rotate":    GizmoMode.ROTATE,
                "scale":     GizmoMode.SCALE,
            }.get(mode, GizmoMode.SELECT)
        self.gizmo_mode = mode
        self._hovered_axis = GizmoAxis.NONE
        self.update()

    def _draw_skybox(self, view, proj) -> None:
        skybox = self._skyboxes.get(self.active_skybox)
        if skybox is not None:
            skybox.draw(self.skybox_shader, view, proj)

    def set_skybox(self, name: str | None) -> None:
        self.active_skybox = name
        # Recomputar IBL cuando cambia el skybox
        from PyQt6.QtCore import QTimer as _QTimer
        _QTimer.singleShot(0, self._compute_ibl_for_active_skybox)
        self.update()

    def _compute_ibl_for_active_skybox(self) -> None:
        """Computa el mapa de irradiance IBL para el skybox activo."""
        if not hasattr(self, 'ibl') or self.ibl is None:
            return
        skybox = self._skyboxes.get(self.active_skybox)
        if skybox is None:
            self.ibl.enabled = False
            self.render_system._skybox_tex = 0
            return
        # Actualizar el skybox texture ID para el specular IBL
        self.render_system._skybox_tex = skybox.texture_id

        # Buscar el directorio de caras del skybox activo
        _sb_root = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "assets", "skyboxes"
        ))
        face_dir = os.path.join(_sb_root, self.active_skybox)
        if not os.path.isdir(face_dir):
            return
        self.makeCurrent()
        try:
            self.ibl.compute_from_face_dir(face_dir, size=32)
        except Exception as _e:
            print(f"[IBL] Error computando irradiance: {_e}")
        finally:
            self.doneCurrent()
        self.update()

    def _draw_grid(self, view, proj) -> None:
        self.grid_shader.use()
        self.grid_shader.set_mat4("uView", view)
        self.grid_shader.set_mat4("uProjection", proj)
        glBindVertexArray(self.grid_vao)
        glDrawArrays(GL_TRIANGLES, 0, 6)
        glBindVertexArray(0)

    # ---------- Ray picking ----------
    def _handle_pick(self, pos: QPoint) -> None:
        """Lanza un rayo desde la cámara por el píxel (pos) y actualiza la selección."""
        if not hasattr(self, 'render_system'):
            return                            # initializeGL aún no ha corrido

        from engine.picking import pick_entity
        aspect = self.width() / max(1, self.height())
        view   = self.camera.view_matrix()
        proj   = self.camera.projection_matrix(aspect)

        eid = pick_entity(
            self.world, self.mesh_registry,
            pos.x(), pos.y(),
            self.width(), self.height(),
            view, proj,
        )

        self.world.selected_entity = eid
        self.entity_picked.emit(eid)
        self.update()

    def _current_ray(self, pos: QPoint):
        """Devuelve (origin, direction) del rayo en el píxel pos."""
        from engine.picking import build_ray
        aspect = self.width() / max(1, self.height())
        view = self.camera.view_matrix()
        proj = self.camera.projection_matrix(aspect)
        return build_ray(pos.x(), pos.y(), self.width(), self.height(), view, proj)

    def _selected_transform(self):
        """Devuelve el Transform de la entidad seleccionada, o None."""
        eid = self.world.selected_entity
        if eid is None or self.gizmo is None:
            return None
        return self.world.get_component(eid, Transform)

    # ---------- Menú contextual del viewport ----------
    def _show_viewport_context_menu(self, event: QMouseEvent) -> None:
        """Clic derecho: selecciona la entidad bajo el cursor y muestra opciones."""
        if not hasattr(self, 'render_system'):
            return

        pos = event.position().toPoint()
        from engine.picking import pick_entity
        aspect = self.width() / max(1, self.height())
        view   = self.camera.view_matrix()
        proj   = self.camera.projection_matrix(aspect)
        eid    = pick_entity(self.world, self.mesh_registry,
                             pos.x(), pos.y(),
                             self.width(), self.height(),
                             view, proj)

        if eid is None:
            return

        # Seleccionar la entidad al hacer clic derecho
        self.world.selected_entity = eid
        self.entity_picked.emit(eid)
        self.update()

        # Mostrar menú contextual
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #252525; color: #dcdcdc; border: 1px solid #3a3a3a; }"
            "QMenu::item { padding: 5px 20px 5px 12px; }"
            "QMenu::item:selected { background: #4a7cb8; }"
            "QMenu::separator { background: #3a3a3a; height: 1px; margin: 3px 6px; }"
        )
        name = self.world.get_entity_name(eid)
        title = menu.addAction(name)
        title.setEnabled(False)
        menu.addSeparator()
        delete_act = menu.addAction("Eliminar entidad")

        chosen = menu.exec(event.globalPosition().toPoint())
        if chosen == delete_act:
            self.delete_entity_requested.emit(eid)

    # ---------- Movimiento WASD ──────────────────────────────────────────
    def _handle_wasd(self, dt: float) -> None:
        """Mueve el target de la cámara con WASD + Shift (subir) + Ctrl (bajar)."""
        K  = Qt.Key
        kw = K.Key_W       in self._keys_pressed
        ks = K.Key_S       in self._keys_pressed
        ka = K.Key_A       in self._keys_pressed
        kd = K.Key_D       in self._keys_pressed
        ku = K.Key_Shift   in self._keys_pressed   # ← Shift izquierdo: subir
        kn = K.Key_Control in self._keys_pressed   # ← Ctrl izquierdo: bajar
        if not (kw or ks or ka or kd or ku or kn):
            return
        if self._gizmo_dragging:
            return

        pos  = self.camera.position
        fwd  = self.camera.target - pos
        dist = float(np.linalg.norm(fwd))
        if dist < 1e-8:
            return
        fwd = (fwd / dist).astype(np.float32)

        # Right perpendicular a forward y al eje Y mundo
        world_up = np.array([0.0, 1.0, 0.0], np.float32)
        right = np.cross(fwd, world_up)
        r_len = float(np.linalg.norm(right))
        right = (right / r_len).astype(np.float32) if r_len > 1e-8 \
                else np.array([1.0, 0.0, 0.0], np.float32)

        # Velocidad proporcional a la distancia × multiplicador del selector
        speed = max(0.5, self.camera.distance) * 2.0 * dt * self._camera_speed

        delta = np.zeros(3, np.float32)
        if kw: delta += fwd      * speed
        if ks: delta -= fwd      * speed
        if kd: delta += right    * speed
        if ka: delta -= right    * speed
        if ku: delta += world_up * speed   # Shift → arriba (eje Y mundo)
        if kn: delta -= world_up * speed   # Ctrl  → abajo

        self.camera.target = (self.camera.target + delta).astype(np.float32)
        self.update()

    # ---------- Input ----------
    def keyPressEvent(self, event) -> None:
        self._keys_pressed.add(event.key())
        # Escape es la ÚNICA manera de salir del modo juego
        if event.key() == Qt.Key.Key_Escape and self._game_state != "stopped":
            p = self.parent()
            while p is not None:
                if hasattr(p, '_on_stop'):
                    p._on_stop()
                    break
                p = p.parent()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        self._keys_pressed.discard(event.key())
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # En modo juego: bloquear completamente la interacción del editor
        if self._game_state != "stopped":
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self._left_press_pos = pos

            # Intento de iniciar drag del gizmo (solo en modos con gizmo)
            t = self._selected_transform()
            if (t is not None
                    and self.gizmo is not None
                    and self.gizmo_mode != GizmoMode.SELECT
                    and hasattr(self, 'render_system')):
                ro, rd = self._current_ray(pos)
                axis = self.gizmo.hit_test(ro, rd, t, self.world,
                                           self.camera.position, self.gizmo_mode)
                if axis != GizmoAxis.NONE:
                    self.gizmo.begin_drag(axis, ro, rd, t, self.world, self.gizmo_mode)
                    self._gizmo_dragging = True

        elif event.button() == Qt.MouseButton.RightButton:
            self._show_viewport_context_menu(event)

        elif event.button() == Qt.MouseButton.MiddleButton:
            self._mmb_pressed = True
            self._last_mouse_pos = event.position().toPoint()
            self._shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._game_state != "stopped":
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self._gizmo_dragging:
                self.gizmo.end_drag()
                self._gizmo_dragging = False
            else:
                pos = event.position().toPoint()
                if self._left_press_pos is not None:
                    dx = pos.x() - self._left_press_pos.x()
                    dy = pos.y() - self._left_press_pos.y()
                    if dx * dx + dy * dy < 25:
                        self._handle_pick(pos)
            self._left_press_pos = None
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._mmb_pressed = False
            self._last_mouse_pos = None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # FPS: consumir el evento para la cámara
        if self._game_state != "stopped":
            if self._game_state == "playing":
                self._handle_fps_mouse(event)
            return   # bloquear toda lógica de editor (órbita, hover gizmo, etc.)

        pos = event.position().toPoint()

        # Drag del gizmo (prioridad sobre órbita)
        if self._gizmo_dragging and self.gizmo is not None:
            eid = self.world.selected_entity
            if eid is not None:
                transform = self.world.get_component(eid, Transform)
                if transform is not None:
                    ro, rd = self._current_ray(pos)
                    self.gizmo.update_drag(ro, rd, transform)
                    # Actualizar inspector sin reconstruirlo
                    parent_win = self.parent()
                    if hasattr(parent_win, 'inspector'):
                        parent_win.inspector.refresh_transform()
                    self.update()
            return

        # Hover highlight del gizmo
        if (not self._mmb_pressed and self.gizmo is not None
                and self.gizmo_mode != GizmoMode.SELECT
                and hasattr(self, 'render_system')):
            t2 = self._selected_transform()
            if t2 is not None:
                ro, rd = self._current_ray(pos)
                axis = self.gizmo.hit_test(ro, rd, t2, self.world,
                                           self.camera.position, self.gizmo_mode)
                if axis != self._hovered_axis:
                    self._hovered_axis = axis
                    self.update()

        if not self._mmb_pressed or self._last_mouse_pos is None:
            return
        pos = event.position().toPoint()
        dx = pos.x() - self._last_mouse_pos.x()
        dy = pos.y() - self._last_mouse_pos.y()
        self._last_mouse_pos = pos

        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if shift:
            self.camera.pan(dx, dy)
        else:
            self.camera.orbit(dx, dy)
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        self.camera.zoom(1 if delta > 0 else -1)
        self.update()
