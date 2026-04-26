"""
Skybox - Cubemap procedural renderizado con depth GL_LEQUAL.

Técnica:
  - Vértice: gl_Position = pos.xyww  →  depth NDC = 1.0 en todos los fragmentos
  - paintGL: primero escena (depth < 1.0), luego skybox con GL_LEQUAL + depthMask=FALSE
  - Resultado: el skybox "rellena" solo el fondo (donde no hay objeto)
"""
import os
import ctypes
import numpy as np
from OpenGL.GL import *
from PIL import Image


# Cubo unidad estándar para skybox — 36 vértices, 6 caras × 2 triángulos
# Las posiciones se usan directamente como coordenadas de dirección para el cubemap.
_VERTS = np.array([
    -1,  1, -1,   -1, -1, -1,    1, -1, -1,    1, -1, -1,    1,  1, -1,   -1,  1, -1,
    -1, -1,  1,   -1, -1, -1,   -1,  1, -1,   -1,  1, -1,   -1,  1,  1,   -1, -1,  1,
     1, -1, -1,    1, -1,  1,    1,  1,  1,    1,  1,  1,    1,  1, -1,    1, -1, -1,
    -1, -1,  1,   -1,  1,  1,    1,  1,  1,    1,  1,  1,    1, -1,  1,   -1, -1,  1,
    -1,  1, -1,    1,  1, -1,    1,  1,  1,    1,  1,  1,   -1,  1,  1,   -1,  1, -1,
    -1, -1, -1,   -1, -1,  1,    1, -1, -1,    1, -1, -1,   -1, -1,  1,    1, -1,  1,
], dtype=np.float32)

_FACE_KEYS = ['px', 'nx', 'py', 'ny', 'pz', 'nz']
_GL_TARGETS = [
    GL_TEXTURE_CUBE_MAP_POSITIVE_X, GL_TEXTURE_CUBE_MAP_NEGATIVE_X,
    GL_TEXTURE_CUBE_MAP_POSITIVE_Y, GL_TEXTURE_CUBE_MAP_NEGATIVE_Y,
    GL_TEXTURE_CUBE_MAP_POSITIVE_Z, GL_TEXTURE_CUBE_MAP_NEGATIVE_Z,
]


class Skybox:
    def __init__(self, face_dir: str):
        """Carga 6 imágenes PNG (px/nx/py/ny/pz/nz) desde face_dir."""
        self._texture = self._load_cubemap(face_dir)
        self._vao, self._vbo = self._create_vao()

    # ------------------------------------------------------------------ #
    def draw(self, shader, view: np.ndarray, proj: np.ndarray) -> None:
        glDepthFunc(GL_LEQUAL)
        glDepthMask(GL_FALSE)

        shader.use()
        shader.set_mat4("uView", view)
        shader.set_mat4("uProjection", proj)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_CUBE_MAP, self._texture)
        glUniform1i(glGetUniformLocation(shader.program, "uSkybox"), 0)

        glBindVertexArray(self._vao)
        glDrawArrays(GL_TRIANGLES, 0, 36)
        glBindVertexArray(0)

        glDepthMask(GL_TRUE)
        glDepthFunc(GL_LESS)

    @property
    def texture_id(self) -> int:
        """ID de la textura GL del cubemap (para IBL)."""
        return self._texture

    def delete(self) -> None:
        glDeleteTextures(1, [self._texture])
        glDeleteVertexArrays(1, [self._vao])
        glDeleteBuffers(1, [self._vbo])

    # ------------------------------------------------------------------ #
    def _load_cubemap(self, face_dir: str) -> int:
        texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_CUBE_MAP, texture)

        for target, key in zip(_GL_TARGETS, _FACE_KEYS):
            path = os.path.join(face_dir, f'{key}.png')
            img = Image.open(path).convert('RGB')
            # OpenGL espera Y=0 abajo; las imágenes PIL tienen Y=0 arriba → flip
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            data = np.array(img, dtype=np.uint8)
            glTexImage2D(target, 0, GL_RGB, img.width, img.height,
                         0, GL_RGB, GL_UNSIGNED_BYTE, data)

        # Generar mipmaps para specular IBL (muestreo por LOD)
        glGenerateMipmap(GL_TEXTURE_CUBE_MAP)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE)
        glBindTexture(GL_TEXTURE_CUBE_MAP, 0)
        return texture

    def _create_vao(self) -> tuple:
        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, _VERTS.nbytes, _VERTS, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)
        return vao, vbo
