"""
PhysicsSystem — física de cuerpo rígido con detección y resolución de colisiones.

Algoritmo:
  1. Integración semi-implícita de Euler:
       v += (gravity si aplica) * dt
       pos += v * dt
  2. Detección de colisiones entre todos los pares de Colliders.
     Formas soportadas: AABB-AABB, Sphere-Sphere, AABB-Sphere.
  3. Resolución de penetración (Linear Projection con slop).
  4. Resolución de velocidades (impulso con coeficiente de restitución).
"""
import numpy as np
from engine.ecs.system import System
from engine.components.transform import Transform
from engine.components.rigidbody import Rigidbody
from engine.components.collider import Collider


_GRAVITY  = np.array([0.0, -9.81, 0.0], dtype=np.float64)
_MAX_DT   = 1.0 / 30.0   # límite superior del paso de tiempo (estabilidad)
_SLOP     = 0.005         # penetración mínima tolerada antes de corregir posición
_BAUMGARTE = 0.6          # fracción de la penetración a corregir por frame


# ── Helpers de geometría ───────────────────────────────────────────────────

def _world_aabb(transform, world, collider):
    """Centro y semiejes del AABB en espacio mundo (sin rotación, solo escala)."""
    wm = transform.world_matrix(world)
    center = wm[3, :3].astype(np.float64) + collider.offset.astype(np.float64)
    # Escala real = norma de cada fila de la sub-matriz 3×3
    sx = float(np.linalg.norm(wm[0, :3]))
    sy = float(np.linalg.norm(wm[1, :3]))
    sz = float(np.linalg.norm(wm[2, :3]))
    half = collider.size.astype(np.float64) * 0.5 * np.array([sx, sy, sz])
    return center, half


def _world_sphere(transform, world, collider):
    """Centro y radio de la esfera en espacio mundo."""
    wm = transform.world_matrix(world)
    center = wm[3, :3].astype(np.float64) + collider.offset.astype(np.float64)
    sx = float(np.linalg.norm(wm[0, :3]))
    sy = float(np.linalg.norm(wm[1, :3]))
    sz = float(np.linalg.norm(wm[2, :3]))
    radius = float(collider.radius) * max(sx, sy, sz)
    return center, radius


def _aabb_vs_aabb(cA, hA, cB, hB):
    """Devuelve (normal, penetración) o (None, None) si no hay colisión."""
    d       = cA - cB
    overlap = hA + hB - np.abs(d)
    if np.any(overlap <= 0.0):
        return None, None
    idx         = int(np.argmin(overlap))
    penetration = float(overlap[idx])
    normal      = np.zeros(3, np.float64)
    normal[idx] = 1.0 if d[idx] > 0 else -1.0
    return normal, penetration


def _sphere_vs_sphere(cA, rA, cB, rB):
    d    = cA - cB
    dist = float(np.linalg.norm(d))
    pen  = rA + rB - dist
    if pen <= 0.0:
        return None, None
    if dist < 1e-9:
        return np.array([0.0, 1.0, 0.0]), pen
    return d / dist, pen


def _aabb_vs_sphere(cBox, hBox, cSph, rSph):
    """AABB es A, esfera es B. Normal apunta de B hacia A (fuera de la esfera)."""
    closest = np.clip(cSph, cBox - hBox, cBox + hBox)
    d       = cSph - closest
    dist    = float(np.linalg.norm(d))
    if dist > rSph:
        return None, None
    if dist < 1e-9:
        # Centro de la esfera dentro del AABB → empujar hacia la cara más cercana
        d_face = hBox - np.abs(cSph - cBox)
        idx    = int(np.argmin(d_face))
        normal = np.zeros(3, np.float64)
        normal[idx] = 1.0 if cSph[idx] > cBox[idx] else -1.0
        return normal, float(rSph + d_face[idx])
    return d / dist, rSph - dist


# ── Resolución ──────────────────────────────────────────────────────────────

def _resolve(tA, rbA, tB, rbB, normal, penetration):
    """Corrige posiciones y aplica impulso de velocidad."""
    invA = 0.0 if (rbA is None or rbA.is_static) else 1.0 / float(rbA.mass)
    invB = 0.0 if (rbB is None or rbB.is_static) else 1.0 / float(rbB.mass)
    invT = invA + invB
    if invT < 1e-12:
        return

    # ── Corrección posicional (Linear Projection) ──────────────────────
    correction = max(penetration - _SLOP, 0.0) / invT * _BAUMGARTE * normal
    if rbA is not None and not rbA.is_static:
        tA.position = (tA.position.astype(np.float64) + correction * invA).astype(np.float32)
    if rbB is not None and not rbB.is_static:
        tB.position = (tB.position.astype(np.float64) - correction * invB).astype(np.float32)

    # ── Impulso de velocidad ────────────────────────────────────────────
    vA = rbA.velocity.astype(np.float64) if (rbA and not rbA.is_static) else np.zeros(3)
    vB = rbB.velocity.astype(np.float64) if (rbB and not rbB.is_static) else np.zeros(3)

    relVel = float(np.dot(vA - vB, normal))
    if relVel >= 0.0:           # objetos ya separándose
        return

    e = 0.0
    if rbA: e = max(e, float(rbA.restitution))
    if rbB: e = max(e, float(rbB.restitution))

    j       = -(1.0 + e) * relVel / invT
    impulse = j * normal

    if rbA and not rbA.is_static:
        rbA.velocity = (vA + impulse * invA).astype(np.float32)
        # Amortiguación de contacto (fricción tangencial simplificada)
        tangent = (vA + impulse * invA)
        tangent -= np.dot(tangent, normal) * normal
        t_len = float(np.linalg.norm(tangent))
        if t_len > 1e-6:
            friction = float(rbA.friction) if rbA else 0.5
            rbA.velocity = rbA.velocity - (tangent / t_len * min(friction * abs(j) * invA, t_len)).astype(np.float32)

    if rbB and not rbB.is_static:
        rbB.velocity = (vB - impulse * invB).astype(np.float32)
        tangent = (vB - impulse * invB)
        tangent -= np.dot(tangent, normal) * normal
        t_len = float(np.linalg.norm(tangent))
        if t_len > 1e-6:
            friction = float(rbB.friction) if rbB else 0.5
            rbB.velocity = rbB.velocity - (tangent / t_len * min(friction * abs(j) * invB, t_len)).astype(np.float32)


# ── Sistema ─────────────────────────────────────────────────────────────────

class PhysicsSystem(System):
    """Actualiza física y detecta/resuelve colisiones cada frame."""

    def __init__(self, world):
        super().__init__(world)
        # Lista de callbacks (eid_a: int, eid_b: int) → llamados en cada colisión
        self.collision_listeners: list = []

    def update(self, dt: float) -> None:
        dt = min(float(dt), _MAX_DT)
        if dt <= 0.0:
            return

        # 1. Integrar dinámica (semi-implicit Euler)
        for eid, (transform, rb) in self.world.query(Transform, Rigidbody):
            if rb.is_static:
                continue

            vel = rb.velocity.astype(np.float64)

            if rb.use_gravity:
                vel += _GRAVITY * dt

            # Actualizar velocidad primero (semi-implícito)
            rb.velocity = vel.astype(np.float32)

            # Luego posición con la velocidad ya actualizada
            transform.position = (transform.position.astype(np.float64) + vel * dt).astype(np.float32)

        # 2. Detectar y resolver colisiones
        self._collide_all()

    # ── Detección ────────────────────────────────────────────────────────
    def _collide_all(self) -> None:
        pairs = []
        for eid, (tr, col) in self.world.query(Transform, Collider):
            rb = self.world.get_component(eid, Rigidbody)
            pairs.append((eid, tr, rb, col))

        for i in range(len(pairs)):
            for j in range(i + 1, len(pairs)):
                eidA, tA, rbA, colA = pairs[i]
                eidB, tB, rbB, colB = pairs[j]

                # Ignorar pares completamente estáticos
                staticA = rbA is None or rbA.is_static
                staticB = rbB is None or rbB.is_static
                if staticA and staticB:
                    continue

                normal, pen = self._detect(tA, colA, tB, colB)
                if normal is not None:
                    _resolve(tA, rbA, tB, rbB, normal, pen)
                    for cb in self.collision_listeners:
                        try:
                            cb(eidA, eidB)
                        except Exception:
                            pass

    def _detect(self, tA, colA, tB, colB):
        sA, sB = colA.shape, colB.shape

        if sA == "aabb" and sB == "aabb":
            cA, hA = _world_aabb(tA, self.world, colA)
            cB, hB = _world_aabb(tB, self.world, colB)
            return _aabb_vs_aabb(cA, hA, cB, hB)

        if sA == "sphere" and sB == "sphere":
            cA, rA = _world_sphere(tA, self.world, colA)
            cB, rB = _world_sphere(tB, self.world, colB)
            return _sphere_vs_sphere(cA, rA, cB, rB)

        # AABB vs Sphere (o Sphere vs AABB invertido)
        if sA == "aabb" and sB == "sphere":
            cBox, hBox = _world_aabb(tA, self.world, colA)
            cSph, rSph = _world_sphere(tB, self.world, colB)
            n, p = _aabb_vs_sphere(cBox, hBox, cSph, rSph)
            # Normal de _aabb_vs_sphere apunta desde caja → esfera;
            # para _resolve necesitamos normal de A hacia B → invertir
            return (-n if n is not None else None), p

        if sA == "sphere" and sB == "aabb":
            cBox, hBox = _world_aabb(tB, self.world, colB)
            cSph, rSph = _world_sphere(tA, self.world, colA)
            return _aabb_vs_sphere(cBox, hBox, cSph, rSph)

        return None, None
