"""
Mesh - Encapsula VAO/VBO/EBO y genera primitivas procedurales.
"""
from OpenGL.GL import *
import numpy as np
import ctypes


class Mesh:
    def __init__(self, vertices: np.ndarray, indices: np.ndarray):
        """
        vertices: array (N, 6) - [x, y, z, nx, ny, nz]
        indices: array de uint32
        """
        self.vertex_count = len(indices)

        # AABB en espacio objeto (calculada antes de subir a GPU).
        # Usada por el sistema de ray-picking. Se expande ligeramente en
        # dimensiones degeneradas (ej: plane en Y=0) para evitar NaN en slab test.
        positions = vertices.reshape(-1, 6)[:, :3]
        self.aabb_min: np.ndarray = positions.min(axis=0).astype(np.float32)
        self.aabb_max: np.ndarray = positions.max(axis=0).astype(np.float32)
        _thin = (self.aabb_max - self.aabb_min) < 1e-3
        self.aabb_min[_thin] -= 5e-4
        self.aabb_max[_thin] += 5e-4

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        glBindVertexArray(self.vao)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

        stride = 6 * 4  # 6 floats * 4 bytes
        # Posición
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        # Normal
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * 4))
        glEnableVertexAttribArray(1)

        glBindVertexArray(0)

    def draw(self) -> None:
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, self.vertex_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def delete(self) -> None:
        glDeleteVertexArrays(1, [self.vao])
        glDeleteBuffers(1, [self.vbo])
        glDeleteBuffers(1, [self.ebo])


def create_cube() -> Mesh:
    """Cubo de lado 1 centrado en el origen, con normales por cara."""
    # 6 caras * 4 vértices, cada uno con su normal
    verts = np.array([
        # Cara +Z (frente)
        -0.5, -0.5,  0.5,  0, 0, 1,
         0.5, -0.5,  0.5,  0, 0, 1,
         0.5,  0.5,  0.5,  0, 0, 1,
        -0.5,  0.5,  0.5,  0, 0, 1,
        # Cara -Z (atrás)
         0.5, -0.5, -0.5,  0, 0, -1,
        -0.5, -0.5, -0.5,  0, 0, -1,
        -0.5,  0.5, -0.5,  0, 0, -1,
         0.5,  0.5, -0.5,  0, 0, -1,
        # Cara +X (derecha)
         0.5, -0.5,  0.5,  1, 0, 0,
         0.5, -0.5, -0.5,  1, 0, 0,
         0.5,  0.5, -0.5,  1, 0, 0,
         0.5,  0.5,  0.5,  1, 0, 0,
        # Cara -X (izquierda)
        -0.5, -0.5, -0.5, -1, 0, 0,
        -0.5, -0.5,  0.5, -1, 0, 0,
        -0.5,  0.5,  0.5, -1, 0, 0,
        -0.5,  0.5, -0.5, -1, 0, 0,
        # Cara +Y (arriba)
        -0.5,  0.5,  0.5,  0, 1, 0,
         0.5,  0.5,  0.5,  0, 1, 0,
         0.5,  0.5, -0.5,  0, 1, 0,
        -0.5,  0.5, -0.5,  0, 1, 0,
        # Cara -Y (abajo)
        -0.5, -0.5, -0.5,  0, -1, 0,
         0.5, -0.5, -0.5,  0, -1, 0,
         0.5, -0.5,  0.5,  0, -1, 0,
        -0.5, -0.5,  0.5,  0, -1, 0,
    ], dtype=np.float32)

    indices = np.array([
        0, 1, 2, 0, 2, 3,         # +Z
        4, 5, 6, 4, 6, 7,         # -Z
        8, 9, 10, 8, 10, 11,      # +X
        12, 13, 14, 12, 14, 15,   # -X
        16, 17, 18, 16, 18, 19,   # +Y
        20, 21, 22, 20, 22, 23,   # -Y
    ], dtype=np.uint32)

    return Mesh(verts, indices)


def create_sphere(radius: float = 0.5, segments: int = 32, rings: int = 16) -> Mesh:
    """Esfera UV procedural."""
    verts = []
    indices = []

    for ring in range(rings + 1):
        phi = np.pi * ring / rings
        for seg in range(segments + 1):
            theta = 2 * np.pi * seg / segments
            x = radius * np.sin(phi) * np.cos(theta)
            y = radius * np.cos(phi)
            z = radius * np.sin(phi) * np.sin(theta)
            # Normal = posición normalizada (es una esfera)
            nx, ny, nz = x / radius, y / radius, z / radius
            verts.extend([x, y, z, nx, ny, nz])

    for ring in range(rings):
        for seg in range(segments):
            a = ring * (segments + 1) + seg
            b = a + segments + 1
            indices.extend([a, b, a + 1, b, b + 1, a + 1])

    return Mesh(np.array(verts, dtype=np.float32), np.array(indices, dtype=np.uint32))


def create_capsule(radius: float = 0.35, height: float = 1.5,
                   seg: int = 16, rings: int = 8) -> Mesh:
    """
    Cápsula centrada en el origen.
    Extiende de y=-(height/2+radius) a y=(height/2+radius).

    Generada como:
      - Semiesfera inferior: de polo sur (phi=-π/2) al ecuador inferior
      - Cilindro: el quad entre ecuador inferior y ecuador superior
      - Semiesfera superior: del ecuador superior al polo norte (phi=π/2)
    """
    half = height / 2.0
    row_data: list[tuple[float, float]] = []

    # Semiesfera inferior: y_center=-half, phi de -π/2 a 0
    for r in range(rings + 1):
        phi = -np.pi / 2 + np.pi / 2 * r / rings
        row_data.append((-half, phi))

    # Semiesfera superior: y_center=+half, phi de π/2/rings a π/2
    # (el ecuador phi=0 ya está en la última fila inferior)
    for r in range(1, rings + 1):
        phi = np.pi / 2 * r / rings
        row_data.append((+half, phi))

    n_rows   = len(row_data)
    n_per_row = seg + 1
    verts = []

    for y_center, phi in row_data:
        xz_r = radius * np.cos(phi)
        y    = y_center + radius * np.sin(phi)
        for s in range(n_per_row):
            theta = 2 * np.pi * s / seg
            x  = xz_r * np.cos(theta)
            z  = xz_r * np.sin(theta)
            nx = np.cos(phi) * np.cos(theta)
            ny = np.sin(phi)
            nz = np.cos(phi) * np.sin(theta)
            verts.extend([x, y, z, nx, ny, nz])

    idxs = []
    for r in range(n_rows - 1):
        for s in range(seg):
            a = r * n_per_row + s
            b = a + 1
            c = (r + 1) * n_per_row + s
            d = c + 1
            idxs.extend([a, b, d, a, d, c])

    return Mesh(np.array(verts, dtype=np.float32),
                np.array(idxs,  dtype=np.uint32))


def create_plane(size: float = 10.0) -> Mesh:
    """Plano horizontal en Y=0."""
    h = size / 2
    verts = np.array([
        -h, 0, -h,  0, 1, 0,
         h, 0, -h,  0, 1, 0,
         h, 0,  h,  0, 1, 0,
        -h, 0,  h,  0, 1, 0,
    ], dtype=np.float32)
    indices = np.array([0, 2, 1, 0, 3, 2], dtype=np.uint32)
    return Mesh(verts, indices)
