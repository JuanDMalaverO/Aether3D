"""
ObjLoader - Carga archivos .obj y devuelve un Mesh listo para OpenGL.

Soporta:
 - v / vn / f (posición, normal, cara)
 - Caras con formato v, v/vt, v//vn, v/vt/vn
 - Quads y n-gons (triangulación por abanico)
 - Normales suaves calculadas automáticamente si el archivo no las incluye
"""
import numpy as np
from engine.rendering.mesh import Mesh


def load_obj(filepath: str) -> Mesh:
    """Lee un .obj y devuelve un Mesh (requiere contexto OpenGL activo)."""
    raw_pos: list = []     # [[x, y, z], ...]
    raw_nrm: list = []     # [[nx, ny, nz], ...]
    face_tris: list = []   # [((pi,ni),(pi,ni),(pi,ni)), ...]

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            tok = parts[0]

            if tok == 'v' and len(parts) >= 4:
                raw_pos.append([float(parts[1]), float(parts[2]), float(parts[3])])

            elif tok == 'vn' and len(parts) >= 4:
                raw_nrm.append([float(parts[1]), float(parts[2]), float(parts[3])])

            elif tok == 'f' and len(parts) >= 4:
                verts = []
                for entry in parts[1:]:
                    segs = entry.split('/')
                    pi = int(segs[0])
                    pi = pi - 1 if pi > 0 else len(raw_pos) + pi
                    ni = None
                    if len(segs) >= 3 and segs[2]:
                        n = int(segs[2])
                        ni = n - 1 if n > 0 else len(raw_nrm) + n
                    verts.append((pi, ni))
                # Triangulación por abanico (válida para polígonos convexos)
                for i in range(1, len(verts) - 1):
                    face_tris.append((verts[0], verts[i], verts[i + 1]))

    if not face_tris:
        raise ValueError(f"'{filepath}' no contiene geometría válida.")

    # Usamos las normales del archivo solo si TODAS las caras las tienen
    all_have_normals = bool(raw_nrm) and all(
        ni is not None for tri in face_tris for _, ni in tri
    )
    if not all_have_normals:
        raw_nrm, face_tris = _smooth_normals(raw_pos, face_tris)

    # Construcción del buffer indexado: cada par único (pos_idx, nrm_idx) = 1 vértice
    vertex_map: dict = {}
    vertices: list = []
    indices: list = []

    for tri in face_tris:
        for pi, ni in tri:
            key = (pi, ni)
            if key not in vertex_map:
                vertex_map[key] = len(vertices)
                nrm = raw_nrm[ni] if ni is not None else [0.0, 1.0, 0.0]
                vertices.append(raw_pos[pi] + list(nrm))
            indices.append(vertex_map[key])

    return Mesh(
        np.array(vertices, dtype=np.float32),
        np.array(indices,  dtype=np.uint32),
    )


def _smooth_normals(positions, face_tris):
    """Calcula normales suaves: promedio de normales de cara por vértice."""
    n = len(positions)
    accum = np.zeros((n, 3), dtype=np.float64)

    new_tris = []
    for tri in face_tris:
        pi0, pi1, pi2 = tri[0][0], tri[1][0], tri[2][0]
        p0 = np.array(positions[pi0])
        p1 = np.array(positions[pi1])
        p2 = np.array(positions[pi2])
        fn = np.cross(p1 - p0, p2 - p0)
        length = np.linalg.norm(fn)
        if length > 1e-12:
            fn /= length
        accum[pi0] += fn
        accum[pi1] += fn
        accum[pi2] += fn
        # normal_idx == position_idx (un normal por posición)
        new_tris.append(((pi0, pi0), (pi1, pi1), (pi2, pi2)))

    normals = []
    for i in range(n):
        nrm = np.linalg.norm(accum[i])
        normals.append((accum[i] / nrm).tolist() if nrm > 1e-12 else [0.0, 1.0, 0.0])

    return normals, new_tris
