"""
ShadowMap — framebuffer de profundidad + matriz luz para shadow mapping.

Técnica:
  1. Pasada de sombra: renderiza la escena desde la luz hacia un FBO
     con textura GL_R32F. El depth shader escribe gl_FragCoord.z
     explícitamente al canal rojo; el depth renderbuffer asegura oclusión
     correcta entre objetos.
  2. Pasada de color: el fragment shader muestrea esa textura R32F y
     compara la profundidad con la del fragmento actual (PCF 3×3).

Se usa QOpenGLFramebufferObject en lugar de glGenFramebuffers/glBindFramebuffer
de PyOpenGL porque en algunos sistemas Windows, PyOpenGL falla al resolver
los punteros de función FBO dentro de un contexto QOpenGLWidget (las extensiones
no se cargan correctamente). Qt resuelve esto internamente.
"""
import numpy as np
import pyrr
from OpenGL.GL import (
    GL_TEXTURE_2D, GL_R32F,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T,
    GL_NEAREST, GL_CLAMP_TO_EDGE,
    GL_TEXTURE0,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    glActiveTexture, glBindTexture, glTexParameteri,
    glViewport, glClear, glClearColor, glGetError, GL_NO_ERROR,
)
from PyQt6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
from PyQt6.QtCore import QSize


# Ortho projection matrix — implementación numpy propia porque la API de
# pyrr no siempre expone create_orthogonal_projection con este nombre.
def _ortho(left, right, bottom, top, near, far) -> np.ndarray:
    dx = right - left;  dy = top - bottom;  dz = far - near
    return np.array([
        [2.0/dx,          0.0,              0.0,            0.0],
        [0.0,             2.0/dy,           0.0,            0.0],
        [0.0,             0.0,              -2.0/dz,        0.0],
        [-(right+left)/dx, -(top+bottom)/dy, -(far+near)/dz, 1.0],
    ], dtype=np.float32)


class ShadowMap:
    SIZE = int(2048)     # resolución del depth map (cuadrado)

    def __init__(self):
        self.enabled: bool  = True
        self.bias:    float = 0.003
        self.light_space_matrix = np.eye(4, dtype=np.float32)

        # Vaciar cola de errores GL preexistentes (defensivo)
        while glGetError() != GL_NO_ERROR:
            pass

        # ── FBO con textura GL_R32F + depth renderbuffer ───────────────
        # Qt gestiona glGenFramebuffers/glBindFramebuffer internamente,
        # lo que evita el fallo de resolución de extensiones de PyOpenGL.
        fmt = QOpenGLFramebufferObjectFormat()
        fmt.setAttachment(QOpenGLFramebufferObject.Attachment.Depth)
        fmt.setTextureTarget(GL_TEXTURE_2D)
        fmt.setInternalTextureFormat(GL_R32F)   # canal R float = valor de profundidad

        self._qfbo = QOpenGLFramebufferObject(QSize(self.SIZE, self.SIZE), fmt)

        if not self._qfbo.isValid():
            raise RuntimeError(
                "No se pudo crear el shadow FBO. "
                "Comprueba que el driver soporta framebuffers (OpenGL 3.3+)."
            )

        # texture() devuelve el ID de la textura de color (GL_R32F)
        self._tex = self._qfbo.texture()

        # Configurar filtros de muestreo
        glBindTexture(GL_TEXTURE_2D, self._tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glBindTexture(GL_TEXTURE_2D, 0)

    # ── Ciclo de render ────────────────────────────────────────────────────
    def begin_pass(self) -> None:
        self._qfbo.bind()                          # bind PyQt6-nativo, sin PyOpenGL FBO
        glViewport(0, 0, self.SIZE, self.SIZE)
        # Limpiar color a 1.0 (= profundidad "lejana") y depth buffer
        glClearColor(1.0, 1.0, 1.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glClearColor(0.15, 0.15, 0.17, 1.0)       # restaurar color de limpieza de la escena

    def end_pass(self) -> None:
        # bindDefault restaura el framebuffer correcto de Qt (no necesariamente 0)
        QOpenGLFramebufferObject.bindDefault()

    def bind_shadow_texture(self, unit: int = 1) -> None:
        glActiveTexture(GL_TEXTURE0 + unit)
        glBindTexture(GL_TEXTURE_2D, self._tex)

    # ── Cálculo de la matriz luz ───────────────────────────────────────────
    def update_light_matrix(self,
                             light_dir: np.ndarray,
                             scene_center: np.ndarray,
                             scene_radius: float = 20.0) -> None:
        ld = light_dir.astype(np.float64)
        ld_n = ld / (np.linalg.norm(ld) + 1e-12)

        dist = scene_radius * 2.5
        eye  = (scene_center - ld_n * dist).astype(np.float32)

        up = np.array([0.0, 1.0, 0.0], np.float32)
        if abs(float(np.dot(ld_n, [0, 1, 0]))) > 0.99:
            up = np.array([1.0, 0.0, 0.0], np.float32)

        light_view = pyrr.matrix44.create_look_at(
            eye, scene_center.astype(np.float32), up, dtype=np.float32)

        r = scene_radius * 1.4
        light_proj = _ortho(-r, r, -r, r, 0.1, dist * 2.0)

        self.light_space_matrix = (light_view @ light_proj).astype(np.float32)

    def delete(self) -> None:
        del self._qfbo
