"""
Gizmo 3D — ejes interactivos de translate / rotate / scale en ESPACIO LOCAL.

Los gizmos se orientan según la rotación del objeto seleccionado. Al arrastrar
un eje se opera sobre los ejes LOCALES del objeto, no sobre los ejes mundo.

Convención de matrices: pyrr row-major (igual que el resto del motor).
"""
import enum
import ctypes
import numpy as np
from OpenGL.GL import *
import pyrr


# ── Enumeraciones públicas ─────────────────────────────────────────────────
class GizmoMode(enum.Enum):
    SELECT    = 0   # solo picking, sin gizmo
    TRANSLATE = 1
    ROTATE    = 2
    SCALE     = 3

# Alias de compatibilidad (código anterior usaba NONE)
GizmoMode.NONE = GizmoMode.SELECT


class GizmoAxis(enum.Enum):
    NONE = 0
    X    = 1
    Y    = 2
    Z    = 3


# ── Constantes de geometría (espacio normalizado del gizmo) ───────────────
_LEN       = 1.00   # longitud del brazo
_SHAFT_END = 0.78   # inicio de la cabeza
_CONE_R    = 0.065  # radio base del cono
_BOX_H     = 0.08   # semilado del cubo de escala
_RING_R    = 0.90   # radio de los anillos

# Hit-test en espacio local del gizmo (sin escala)
_HIT_HALF  = 0.13
_HIT_START = 0.10
_HIT_END   = _LEN + 0.24

# Colores X=rojo, Y=verde, Z=azul
_COLORS = {
    GizmoAxis.X: np.array([0.95, 0.18, 0.18], np.float32),
    GizmoAxis.Y: np.array([0.18, 0.90, 0.18], np.float32),
    GizmoAxis.Z: np.array([0.22, 0.42, 1.00], np.float32),
}
_COLOR_HOVER = np.array([1.0, 0.85, 0.1], np.float32)
_AXIS_IDX = {GizmoAxis.X: 0, GizmoAxis.Y: 1, GizmoAxis.Z: 2}


# ── Geometría procedural ──────────────────────────────────────────────────
def _upload(verts: np.ndarray):
    vao = glGenVertexArrays(1)
    vbo = glGenBuffers(1)
    glBindVertexArray(vao)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
    glEnableVertexAttribArray(0)
    glBindVertexArray(0)
    return vao, vbo, len(verts) // 3


def _cone_verts(N=10):
    tip, base_x = _LEN, _SHAFT_END
    v = []
    for i in range(N):
        a1 = 2*np.pi*i/N;     a2 = 2*np.pi*(i+1)/N
        y1, z1 = _CONE_R*np.cos(a1), _CONE_R*np.sin(a1)
        y2, z2 = _CONE_R*np.cos(a2), _CONE_R*np.sin(a2)
        v += [tip,0,0, base_x,y1,z1, base_x,y2,z2]
        v += [base_x,0,0, base_x,y2,z2, base_x,y1,z1]
    return np.array(v, np.float32)


def _box_verts():
    h = _BOX_H;  x0, x1 = _SHAFT_END, _LEN
    c = np.array([[x0,-h,-h],[x1,-h,-h],[x1,h,-h],[x0,h,-h],
                  [x0,-h, h],[x1,-h, h],[x1,h, h],[x0,h, h]], np.float32)
    tri = [0,2,1, 0,3,2, 4,5,6, 4,6,7,
           0,1,5, 0,5,4, 2,3,7, 2,7,6,
           0,4,7, 0,7,3, 1,2,6, 1,6,5]
    return c[tri].flatten().astype(np.float32)


def _ring_verts(N=64):
    v = []
    for i in range(N):
        a1 = 2*np.pi*i/N;  a2 = 2*np.pi*(i+1)/N
        v += [_RING_R*np.cos(a1), 0, _RING_R*np.sin(a1),
              _RING_R*np.cos(a2), 0, _RING_R*np.sin(a2)]
    return np.array(v, np.float32)


def _shaft_verts():
    return np.array([0,0,0, _SHAFT_END,0,0], np.float32)


# ── Rotaciones de eje (verificadas empíricamente contra pyrr) ──────────────
# En pyrr: v_row @ R da el resultado correcto, idéntico a lo que aplica OpenGL.
# Rz(-π/2): +X → +Y   |   Ry(+π/2): +X → +Z
# Rz(+π/2): +Y → +X   |   Rx(-π/2): +Y → +Z  (para anillos)
def _rot_arrow(axis: GizmoAxis) -> np.ndarray:
    if axis == GizmoAxis.X:
        return np.eye(4, dtype=np.float32)
    elif axis == GizmoAxis.Y:
        return pyrr.matrix44.create_from_z_rotation(-np.pi/2, dtype=np.float32)
    else:
        return pyrr.matrix44.create_from_y_rotation(np.pi/2, dtype=np.float32)


def _rot_ring(axis: GizmoAxis) -> np.ndarray:
    if axis == GizmoAxis.Y:
        return np.eye(4, dtype=np.float32)
    elif axis == GizmoAxis.X:
        return pyrr.matrix44.create_from_z_rotation(np.pi/2, dtype=np.float32)
    else:
        return pyrr.matrix44.create_from_x_rotation(-np.pi/2, dtype=np.float32)


# ── Helpers matemáticos ───────────────────────────────────────────────────
def _closest_t(ray_o, ray_d, axis_pt, axis_d):
    """Parámetro t a lo largo de axis_d para la mínima distancia al rayo."""
    w = ray_o - axis_pt
    b = float(np.dot(ray_d, axis_d))
    f = float(np.dot(ray_d, w))
    g = float(np.dot(axis_d, w))
    denom = 1.0 - b*b
    return (b*f - g) / denom if abs(denom) > 1e-10 else None


def _ray_plane(ray_o, ray_d, normal, pt):
    denom = float(np.dot(ray_d, normal))
    if abs(denom) < 1e-10:
        return None
    t = float(np.dot(pt - ray_o, normal)) / denom
    return (ray_o + t * ray_d) if t >= 0 else None


def _extract_rotation_pyrr(world_mat: np.ndarray) -> np.ndarray:
    """Extrae la rotación pura (sin escala ni traslación) de la world_matrix pyrr.
    Las filas 0-2 contienen los ejes locales escalados; los normalizamos."""
    rot = np.eye(4, dtype=np.float32)
    for i in range(3):
        row = world_mat[i, :3].copy()
        n = np.linalg.norm(row)
        rot[i, :3] = row / n if n > 1e-10 else row
    return rot


def _local_axis_world(world_mat: np.ndarray, axis: GizmoAxis) -> np.ndarray:
    """Vector unitario del eje LOCAL indicado expresado en espacio mundo."""
    row = world_mat[_AXIS_IDX[axis], :3].copy()
    n = np.linalg.norm(row)
    return (row / n).astype(np.float32) if n > 1e-10 else np.eye(3)[_AXIS_IDX[axis]].astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════
class Gizmo:
    """Gizmo 3D en espacio local del objeto."""

    def __init__(self):
        self._shaft_vao, self._shaft_vbo, _         = _upload(_shaft_verts())
        self._cone_vao,  self._cone_vbo,  self._nc  = _upload(_cone_verts())
        self._box_vao,   self._box_vbo,   self._nb  = _upload(_box_verts())
        self._ring_vao,  self._ring_vbo,  self._nr  = _upload(_ring_verts())

        self._dragging       = False
        self._drag_axis      = GizmoAxis.NONE
        self._drag_mode      = GizmoMode.SELECT
        self._drag_anchor    = None    # posición mundo fija al inicio del drag
        self._drag_local_dir = None    # eje LOCAL en espacio mundo (unit vector)
        self._drag_prev_t    = 0.0
        self._drag_prev_hit  = None

    # ── Utilidades ────────────────────────────────────────────────────────
    def gizmo_scale(self, entity_pos: np.ndarray, camera_pos: np.ndarray) -> float:
        return max(0.5, float(np.linalg.norm(camera_pos - entity_pos)) * 0.20)

    def _base_model(self, transform, world, gizmo_scale: float, entity_pos: np.ndarray):
        """Matriz base del gizmo: rotación local pura del objeto × escala × traslación."""
        wm   = transform.world_matrix(world)
        rot  = _extract_rotation_pyrr(wm)
        S    = pyrr.matrix44.create_from_scale([gizmo_scale]*3, dtype=np.float32)
        T    = pyrr.matrix44.create_from_translation(entity_pos.astype(np.float32),
                                                      dtype=np.float32)
        return rot @ S @ T

    # ── API pública ────────────────────────────────────────────────────────
    def draw(self, shader, view: np.ndarray, proj: np.ndarray,
             transform, world,
             camera_pos: np.ndarray, mode: GizmoMode,
             hovered: GizmoAxis = GizmoAxis.NONE) -> None:
        if mode == GizmoMode.SELECT:
            return

        wm         = transform.world_matrix(world)
        entity_pos = wm[3, :3].astype(np.float32)
        scale      = self.gizmo_scale(entity_pos, camera_pos)
        base       = self._base_model(transform, world, scale, entity_pos)

        glDisable(GL_DEPTH_TEST)
        glLineWidth(1)
        shader.use()
        shader.set_mat4("uView", view)
        shader.set_mat4("uProjection", proj)

        for axis in (GizmoAxis.X, GizmoAxis.Y, GizmoAxis.Z):
            color = _COLOR_HOVER if axis == hovered else _COLORS[axis]
            shader.set_vec3("uColor", color)

            R     = _rot_ring(axis) if mode == GizmoMode.ROTATE else _rot_arrow(axis)
            model = R @ base
            shader.set_mat4("uModel", model)

            glBindVertexArray(self._shaft_vao)
            glDrawArrays(GL_LINES, 0, 2)

            if mode == GizmoMode.TRANSLATE:
                glBindVertexArray(self._cone_vao)
                glDrawArrays(GL_TRIANGLES, 0, self._nc)
            elif mode == GizmoMode.SCALE:
                glBindVertexArray(self._box_vao)
                glDrawArrays(GL_TRIANGLES, 0, self._nb)
            else:
                glBindVertexArray(self._ring_vao)
                glDrawArrays(GL_LINES, 0, self._nr)

        glLineWidth(1.0)
        glEnable(GL_DEPTH_TEST)
        glBindVertexArray(0)

    def hit_test(self, ray_o: np.ndarray, ray_d: np.ndarray,
                 transform, world,
                 camera_pos: np.ndarray, mode: GizmoMode) -> GizmoAxis:
        """Hit-test en el ESPACIO LOCAL del gizmo.

        Transforma el rayo al espacio local (entidad sin escala ni traslación),
        y prueba contra AABB alineadas con los ejes locales del gizmo.
        """
        if mode == GizmoMode.SELECT:
            return GizmoAxis.NONE

        wm         = transform.world_matrix(world)
        entity_pos = wm[3, :3].astype(np.float32)
        scale      = self.gizmo_scale(entity_pos, camera_pos)
        base       = self._base_model(transform, world, scale, entity_pos)
        inv_base   = np.linalg.inv(base)

        # Transformar rayo al espacio local del gizmo (row-major pyrr)
        lo_h = np.array([*ray_o, 1.0], np.float32) @ inv_base
        ld_h = np.array([*ray_d, 0.0], np.float32) @ inv_base
        lo   = lo_h[:3] / lo_h[3]
        ln   = np.linalg.norm(ld_h[:3])
        if ln < 1e-10:
            return GizmoAxis.NONE
        ld = ld_h[:3] / ln

        from engine.picking import ray_vs_aabb
        S, E, H = _HIT_START, _HIT_END, _HIT_HALF

        if mode == GizmoMode.ROTATE:
            Rf, Rt = _RING_R + 0.15, 0.12
            boxes = [
                (GizmoAxis.X, np.array([-Rt,-Rf,-Rf]), np.array([ Rt, Rf, Rf])),
                (GizmoAxis.Y, np.array([-Rf,-Rt,-Rf]), np.array([ Rf, Rt, Rf])),
                (GizmoAxis.Z, np.array([-Rf,-Rf,-Rt]), np.array([ Rf, Rf, Rt])),
            ]
        else:
            boxes = [
                (GizmoAxis.X, np.array([ S,-H,-H]), np.array([ E, H, H])),
                (GizmoAxis.Y, np.array([-H, S,-H]), np.array([ H, E, H])),
                (GizmoAxis.Z, np.array([-H,-H, S]), np.array([ H, H, E])),
            ]

        best_t, best_axis = float('inf'), GizmoAxis.NONE
        for axis, mn, mx in boxes:
            t = ray_vs_aabb(lo, ld, mn.astype(np.float32), mx.astype(np.float32))
            if t is not None and 0 <= t < best_t:
                best_t, best_axis = t, axis

        return best_axis

    def begin_drag(self, axis: GizmoAxis, ray_o: np.ndarray, ray_d: np.ndarray,
                   transform, world, mode: GizmoMode) -> None:
        wm         = transform.world_matrix(world)
        entity_pos = wm[3, :3].astype(np.float32)

        self._dragging       = True
        self._drag_axis      = axis
        self._drag_mode      = mode
        self._drag_anchor    = entity_pos.copy()
        # Eje LOCAL del objeto en espacio mundo (unit vector)
        self._drag_local_dir = _local_axis_world(wm, axis)

        if mode in (GizmoMode.TRANSLATE, GizmoMode.SCALE):
            self._drag_prev_t = _closest_t(ray_o, ray_d, entity_pos, self._drag_local_dir) or 0.0
        else:
            self._drag_prev_hit = _ray_plane(ray_o, ray_d, self._drag_local_dir, entity_pos)

    def update_drag(self, ray_o: np.ndarray, ray_d: np.ndarray, transform) -> None:
        if not self._dragging or self._drag_local_dir is None:
            return

        adir   = self._drag_local_dir   # eje LOCAL en espacio mundo
        aidx   = _AXIS_IDX[self._drag_axis]
        anchor = self._drag_anchor

        if self._drag_mode == GizmoMode.TRANSLATE:
            t = _closest_t(ray_o, ray_d, anchor, adir)
            if t is None: return
            transform.position = transform.position + adir * (t - self._drag_prev_t)
            self._drag_prev_t  = t

        elif self._drag_mode == GizmoMode.SCALE:
            t = _closest_t(ray_o, ray_d, anchor, adir)
            if t is None: return
            transform.scale[aidx] = max(0.001, transform.scale[aidx] + (t - self._drag_prev_t))
            self._drag_prev_t = t

        elif self._drag_mode == GizmoMode.ROTATE:
            curr = _ray_plane(ray_o, ray_d, adir, anchor)
            prev = self._drag_prev_hit
            if curr is None or prev is None: return
            v1 = prev - anchor;  v2 = curr - anchor
            l1, l2 = np.linalg.norm(v1), np.linalg.norm(v2)
            if l1 < 1e-8 or l2 < 1e-8: return
            v1, v2 = v1/l1, v2/l2
            cos_a = float(np.clip(np.dot(v1, v2), -1, 1))
            sign  = float(np.sign(np.dot(np.cross(v1, v2), adir)))
            transform.rotation[aidx] += np.degrees(np.arccos(cos_a)) * sign
            self._drag_prev_hit = curr

    def end_drag(self) -> None:
        self._dragging       = False
        self._drag_axis      = GizmoAxis.NONE
        self._drag_local_dir = None

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    def delete(self) -> None:
        for vao in (self._shaft_vao, self._cone_vao, self._box_vao, self._ring_vao):
            glDeleteVertexArrays(1, [vao])
        for vbo in (self._shaft_vbo, self._cone_vbo, self._box_vbo, self._ring_vbo):
            glDeleteBuffers(1, [vbo])
