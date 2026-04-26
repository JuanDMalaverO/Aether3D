"""
Ray picking — selección de entidades por clic en el viewport.

Convención de matrices: pyrr usa row-major. Para transformar un punto
en espacio objeto a espacio mundo se hace: world_row = obj_row @ model_pyrr
(igual que en el vertex shader vía su transposición a column-major en OpenGL).

Flujo:
  1. build_ray(px, py, w, h, view, proj)  →  (origin, direction)
  2. Para cada entidad visible:
       world_aabb = transform_aabb(mesh.aabb_min, mesh.aabb_max, world_matrix)
       t = ray_vs_aabb(origin, direction, world_aabb)
  3. Devolver la entidad con menor t (más cercana a la cámara).
"""
import numpy as np
from engine.ecs import World
from engine.components.transform import Transform
from engine.components.mesh import MeshRenderer


# ──────────────────────────────────────────────────────────────────────
def build_ray(
    px: int, py: int, w: int, h: int,
    view: np.ndarray, proj: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Construye (origin, direction) del rayo que pasa por el píxel (px, py).

    La operación de unproject sigue la convención pyrr row-major:
        clip_row = world_row  @  view  @  proj
        world_row = clip_row  @  inv(view @ proj)
    """
    # NDC: x∈[-1,1], y∈[-1,1] con y↑ (pantalla tiene y↓)
    x_ndc = (2.0 * px / w) - 1.0
    y_ndc = 1.0 - (2.0 * py / h)

    vp     = view @ proj
    inv_vp = np.linalg.inv(vp)

    def unproject(z_ndc: float) -> np.ndarray:
        clip = np.array([x_ndc, y_ndc, z_ndc, 1.0])
        world_h = clip @ inv_vp        # row vector × matrix (pyrr row-major)
        return world_h[:3] / world_h[3]

    near = unproject(-1.0).astype(np.float32)
    far  = unproject( 1.0).astype(np.float32)

    delta = far - near
    length = np.linalg.norm(delta)
    direction = delta / length if length > 1e-10 else np.array([0, 0, -1], np.float32)

    return near, direction


# ──────────────────────────────────────────────────────────────────────
def ray_vs_aabb(
    origin: np.ndarray,
    direction: np.ndarray,
    aabb_min: np.ndarray,
    aabb_max: np.ndarray,
) -> float | None:
    """Slab method: devuelve t de entrada (≥0) o None si no intersecta."""
    # Evitar división por cero manteniendo el signo
    safe_dir = np.where(np.abs(direction) > 1e-12, direction,
                        np.copysign(1e-12, direction + 1e-30))
    inv = 1.0 / safe_dir

    t1 = (aabb_min - origin) * inv
    t2 = (aabb_max - origin) * inv

    t_enter = np.minimum(t1, t2).max()
    t_exit  = np.maximum(t1, t2).min()

    if t_exit < 0.0 or t_enter > t_exit:
        return None
    return float(t_enter) if t_enter >= 0.0 else float(t_exit)


# ──────────────────────────────────────────────────────────────────────
def _world_aabb(
    obj_min: np.ndarray,
    obj_max: np.ndarray,
    world_mat: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Transforma el AABB de espacio objeto a espacio mundo.

    Transforma las 8 esquinas con la convención row-major de pyrr
    (corner_row @ world_mat) y toma min/max del resultado.
    """
    mn, mx = obj_min, obj_max
    corners = np.array([
        [mn[0], mn[1], mn[2], 1.0],
        [mx[0], mn[1], mn[2], 1.0],
        [mn[0], mx[1], mn[2], 1.0],
        [mx[0], mx[1], mn[2], 1.0],
        [mn[0], mn[1], mx[2], 1.0],
        [mx[0], mn[1], mx[2], 1.0],
        [mn[0], mx[1], mx[2], 1.0],
        [mx[0], mx[1], mx[2], 1.0],
    ], dtype=np.float32)           # (8, 4)

    world_h  = corners @ world_mat  # (8, 4) — row-major pyrr
    world_xyz = world_h[:, :3] / world_h[:, 3:4]
    return world_xyz.min(axis=0), world_xyz.max(axis=0)


# ──────────────────────────────────────────────────────────────────────
def pick_entity(
    world: World,
    mesh_registry: dict,
    px: int, py: int,
    viewport_w: int, viewport_h: int,
    view: np.ndarray,
    proj: np.ndarray,
) -> int | None:
    """Selecciona la entidad más cercana bajo el píxel (px, py).

    Itera todas las entidades con Transform + MeshRenderer, calcula la AABB
    en espacio mundo y devuelve el entity_id con menor t de intersección,
    o None si el clic fue en vacío.
    """
    origin, direction = build_ray(px, py, viewport_w, viewport_h, view, proj)

    best_t   = float('inf')
    best_eid = None

    for eid, (transform, mr) in world.query(Transform, MeshRenderer):
        if not mr.visible:
            continue
        mesh = mesh_registry.get(mr.mesh_name)
        if mesh is None or not hasattr(mesh, 'aabb_min'):
            continue

        world_mat       = transform.world_matrix(world)
        w_min, w_max    = _world_aabb(mesh.aabb_min, mesh.aabb_max, world_mat)
        t               = ray_vs_aabb(origin, direction, w_min, w_max)

        if t is not None and 0.0 <= t < best_t:
            best_t   = t
            best_eid = eid

    return best_eid
