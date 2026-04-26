"""
ParticleSystem — actualiza y renderiza partículas con GPU instancing.

Arquitectura:
  ParticleEmitter (componente) → configuración pura, sin estado GL.
  _EmitterState  (interno)     → arrays CPU de partículas + VAO/VBO GPU.
  ParticleSystem (sistema)     → crea/actualiza/dibuja _EmitterState por entidad.

Render: un único glDrawArraysInstanced por emisor.
Layout del buffer instanciado (36 bytes / partícula):
  [px, py, pz,  size,  r, g, b, a,  rot]
  loc1 (vec3)   loc2   loc3 (vec4)  loc4
"""
import ctypes
import json
import os

import numpy as np
from OpenGL.GL import *

from engine.components.particle_emitter import ParticleEmitter
from engine.components.transform import Transform


# ── Estado de un emisor individual ────────────────────────────────────────

class _EmitterState:
    _STRIDE = 9 * 4   # 9 floats × 4 bytes = 36 bytes por partícula

    def __init__(self, max_particles: int):
        self.max_particles = max_particles

        # Arrays CPU (todos pre-allocados al máximo)
        n = max_particles
        self.positions  = np.zeros((n, 3), np.float32)
        self.velocities = np.zeros((n, 3), np.float32)
        self.ages       = np.zeros(n, np.float32)
        self.lifetimes  = np.zeros(n, np.float32)
        self.rotations  = np.zeros(n, np.float32)
        self.spin_rates = np.zeros(n, np.float32)
        self.alive      = np.zeros(n, bool)

        # Buffer de instancias que se sube a GPU
        self._inst_buf  = np.zeros((n, 9), np.float32)
        self._alive_cnt = 0

        # Estado interno de emisión
        self._acc        = 0.0    # acumulador de emisión fraccional
        self._burst_done = False

        self._init_gl()

    # ── GL setup ──────────────────────────────────────────────────────
    def _init_gl(self) -> None:
        quad = np.array([
            -0.5, -0.5,   0.5, -0.5,   0.5,  0.5,
            -0.5, -0.5,   0.5,  0.5,  -0.5,  0.5,
        ], dtype=np.float32)

        self._vao      = glGenVertexArrays(1)
        self._quad_vbo = glGenBuffers(1)
        self._inst_vbo = glGenBuffers(1)

        glBindVertexArray(self._vao)

        # ── Quad (por vértice) ─────────────────────────────────────
        glBindBuffer(GL_ARRAY_BUFFER, self._quad_vbo)
        glBufferData(GL_ARRAY_BUFFER, quad.nbytes, quad, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 8, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        # divisor 0 → avanza por vértice (comportamiento por defecto)

        # ── Instancias (por partícula) ─────────────────────────────
        glBindBuffer(GL_ARRAY_BUFFER, self._inst_vbo)
        glBufferData(GL_ARRAY_BUFFER,
                     self.max_particles * self._STRIDE,
                     None, GL_DYNAMIC_DRAW)

        s = self._STRIDE
        # loc 1: posición (vec3, offset 0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1); glVertexAttribDivisor(1, 1)
        # loc 2: tamaño (float, offset 12)
        glVertexAttribPointer(2, 1, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(12))
        glEnableVertexAttribArray(2); glVertexAttribDivisor(2, 1)
        # loc 3: color RGBA (vec4, offset 16)
        glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(16))
        glEnableVertexAttribArray(3); glVertexAttribDivisor(3, 1)
        # loc 4: rotación (float, offset 32)
        glVertexAttribPointer(4, 1, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(32))
        glEnableVertexAttribArray(4); glVertexAttribDivisor(4, 1)

        glBindVertexArray(0)

    # ── Actualización CPU ──────────────────────────────────────────────
    def update(self, em: ParticleEmitter, world_pos: np.ndarray, dt: float) -> None:
        alive_f = self.alive.astype(np.float32)   # 1.0 si viva, 0.0 si muerta

        # Envejecer
        self.ages += dt * alive_f

        # Matar expiradas
        died = self.alive & (self.ages >= self.lifetimes)
        self.alive[died] = False

        # Actualizar física (vectorizado; muertos tienen alive_f=0 → no contribution)
        alive_f = self.alive.astype(np.float32)   # recalcular tras muertes
        self.velocities[:, 1] -= em.gravity_scale * 9.81 * dt * alive_f
        self.positions += self.velocities * dt * alive_f[:, np.newaxis]
        self.rotations += self.spin_rates * dt * alive_f

        # Emisión
        if em.burst:
            if not self._burst_done:
                for _ in range(em.burst_count):
                    self._spawn(em, world_pos)
                self._burst_done = True
        else:
            self._acc += em.emission_rate * dt
            count = int(self._acc)
            self._acc -= count
            for _ in range(count):
                self._spawn(em, world_pos)

        self._build_and_upload(em)

    def _spawn(self, em: ParticleEmitter, origin: np.ndarray) -> None:
        dead = np.where(~self.alive)[0]
        if len(dead) == 0:
            return
        i = dead[0]

        self.alive[i]     = True
        self.ages[i]      = 0.0
        self.lifetimes[i] = float(np.random.uniform(em.lifetime_min, em.lifetime_max))
        self.spin_rates[i] = float(np.random.uniform(-1.5, 1.5))
        self.rotations[i]  = float(np.random.uniform(0, 2 * np.pi))

        # Posición y dirección según forma
        if em.shape == "point":
            self.positions[i] = origin
            dir_v = _rand_unit()

        elif em.shape == "sphere":
            dir_v = _rand_unit()
            r = float(np.random.uniform(0, em.shape_radius))
            self.positions[i] = origin + dir_v * r
            dir_v = _rand_unit()          # velocidad independiente de posición

        else:  # "cone" — emite hacia arriba (+Y)
            half = np.radians(em.cone_angle)
            theta = float(np.random.uniform(0, half))
            phi   = float(np.random.uniform(0, 2 * np.pi))
            st    = np.sin(theta)
            dir_v = np.array([st * np.cos(phi), np.cos(theta), st * np.sin(phi)], np.float32)
            r = float(np.random.uniform(0, em.shape_radius))
            self.positions[i] = origin + np.array([
                st * np.cos(phi), 0, st * np.sin(phi)], np.float32) * r

        speed = float(np.random.uniform(em.speed_min, em.speed_max))
        self.velocities[i] = dir_v * speed

    def _build_and_upload(self, em: ParticleEmitter) -> None:
        idx = np.where(self.alive)[0]
        self._alive_cnt = len(idx)
        if self._alive_cnt == 0:
            return

        t = np.clip(self.ages[idx] / np.maximum(self.lifetimes[idx], 1e-8), 0.0, 1.0)

        cs = em.color_start.astype(np.float64)
        ce = em.color_end.astype(np.float64)

        data = self._inst_buf[:self._alive_cnt]
        data[:, 0:3] = self.positions[idx]
        data[:, 3]   = em.size_start + (em.size_end - em.size_start) * t
        data[:, 4:8] = cs + (ce - cs) * t[:, np.newaxis]
        data[:, 8]   = self.rotations[idx]

        glBindBuffer(GL_ARRAY_BUFFER, self._inst_vbo)
        glBufferSubData(GL_ARRAY_BUFFER, 0, data.nbytes, data)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    # ── Render ────────────────────────────────────────────────────────
    def draw(self) -> None:
        if self._alive_cnt <= 0:
            return
        glBindVertexArray(self._vao)
        glDrawArraysInstanced(GL_TRIANGLES, 0, 6, self._alive_cnt)
        glBindVertexArray(0)

    def delete(self) -> None:
        glDeleteVertexArrays(1, [self._vao])
        glDeleteBuffers(1, [self._quad_vbo])
        glDeleteBuffers(1, [self._inst_vbo])

    def reset(self) -> None:
        """Reinicia todas las partículas (para stop de Play)."""
        self.alive[:] = False
        self._alive_cnt = 0
        self._acc = 0.0
        self._burst_done = False


# ── Helpers ────────────────────────────────────────────────────────────────

def _rand_unit() -> np.ndarray:
    v = np.random.randn(3).astype(np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-8 else np.array([0, 1, 0], np.float32)


# ── Sistema principal ──────────────────────────────────────────────────────

class ParticleSystem:
    """Gestiona todos los ParticleEmitter activos usando GPU instancing."""

    def __init__(self, world, shader):
        self._world  = world
        self._shader = shader
        self._states: dict[int, _EmitterState] = {}

    # ── Actualización ──────────────────────────────────────────────────
    def update(self, dt: float) -> None:
        active_eids = set()

        for eid, (tr, em) in self._world.query(Transform, ParticleEmitter):
            active_eids.add(eid)
            if not em.enabled:
                continue

            # Crear o recrear estado si max_particles cambió
            state = self._states.get(eid)
            if state is None or state.max_particles != em.max_particles:
                if state:
                    state.delete()
                self._states[eid] = _EmitterState(em.max_particles)
                state = self._states[eid]

            wm = tr.world_matrix(self._world)
            world_pos = wm[3, :3].astype(np.float32)
            state.update(em, world_pos, dt)

        # Limpiar estados huérfanos
        for eid in list(self._states):
            if eid not in active_eids:
                self._states[eid].delete()
                del self._states[eid]

    def stop_all(self) -> None:
        """Reinicia todas las partículas (llamado al salir del modo juego)."""
        for state in self._states.values():
            state.reset()

    # ── Render ─────────────────────────────────────────────────────────
    def draw(self, view: np.ndarray, proj: np.ndarray) -> None:
        if not self._states:
            return

        # Extraer right y up de la cámara (filas 0 y 1 de la view row-major)
        cam_right = view[0, :3].astype(np.float32)
        cam_up    = view[1, :3].astype(np.float32)

        self._shader.use()
        self._shader.set_mat4("uView",       view)
        self._shader.set_mat4("uProjection", proj)
        self._shader.set_vec3("uCamRight",   cam_right)
        self._shader.set_vec3("uCamUp",      cam_up)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)       # additive para fuego/explosión
        glDepthMask(GL_FALSE)                   # leer depth pero no escribir

        for eid, state in self._states.items():
            em = self._world.get_component(eid, ParticleEmitter)
            if em and em.enabled:
                # Blend mode por emisor: additive o normal
                if getattr(em, '_blend_additive', True):
                    glBlendFunc(GL_SRC_ALPHA, GL_ONE)
                else:
                    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                state.draw()

        glDepthMask(GL_TRUE)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)  # restaurar blend

    def delete(self) -> None:
        for state in self._states.values():
            state.delete()
        self._states.clear()


# ── Carga de presets ───────────────────────────────────────────────────────

def apply_preset(path: str, emitter: ParticleEmitter) -> None:
    """Lee un JSON de preset y aplica sus valores al emisor."""
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)

    for key, val in data.items():
        if not hasattr(emitter, key):
            continue
        if key in ('color_start', 'color_end'):
            setattr(emitter, key, np.array(val, np.float32))
        else:
            setattr(emitter, key, val)


def list_presets(presets_dir: str) -> list[tuple[str, str]]:
    """Devuelve [(nombre, ruta)] de los presets disponibles."""
    if not os.path.isdir(presets_dir):
        return []
    result = []
    for fn in sorted(os.listdir(presets_dir)):
        if fn.endswith('.json'):
            name = os.path.splitext(fn)[0]
            result.append((name, os.path.join(presets_dir, fn)))
    return result
