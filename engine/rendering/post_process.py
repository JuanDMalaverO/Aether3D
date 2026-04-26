"""
PostProcess — pipeline de post-procesado de pantalla completa.

Flujo:
  begin() → la escena se renderiza al FBO offscreen (GL_RGBA16F)
  end()   → un quad NDC aplica los efectos y vuelca al framebuffer por defecto

Efectos independientes (toggleables en tiempo real):
  - Tonemapping ACES filmic  (comprime HDR, evita saturación)
  - Vignette                 (oscurece bordes)
  - FXAA                     (antialiasing espacial en post)

Extensibilidad: añadir un uniforme uNuevoEfecto en post.frag y su flag aquí.
"""
import ctypes
import numpy as np
from OpenGL.GL import (
    GL_TEXTURE_2D, GL_RGBA16F,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T,
    GL_LINEAR, GL_CLAMP_TO_EDGE,
    GL_TEXTURE0,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_FLOAT, GL_ARRAY_BUFFER, GL_STATIC_DRAW,
    GL_TRIANGLES,
    GL_DEPTH_TEST,
    glActiveTexture, glBindTexture, glTexParameteri,
    glViewport, glClear, glClearColor,
    glGenVertexArrays, glGenBuffers,
    glBindVertexArray, glBindBuffer, glBufferData,
    glVertexAttribPointer, glEnableVertexAttribArray,
    glDrawArrays, glDisable, glEnable,
    glGetError, GL_NO_ERROR,
)
from PyQt6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
from PyQt6.QtCore import QSize


class PostProcess:
    """Pipeline de post-procesado con FBO Qt y efectos configurables."""

    def __init__(self, width: int, height: int, shader):
        # ── Estado de efectos ──────────────────────────────────────────
        self.enabled            = True
        self.tonemap_enabled    = True
        self.vignette_enabled   = False
        self.fxaa_enabled       = False
        self.exposure           = 1.0
        self.vignette_intensity = 1.5

        self._shader = shader
        self._width  = max(1, int(width))
        self._height = max(1, int(height))
        self._fbo    = None
        self._tex    = 0
        self._vao    = None

        self._create_fbo(self._width, self._height)
        self._create_quad()

    # ── FBO ───────────────────────────────────────────────────────────────
    def _create_fbo(self, w: int, h: int) -> None:
        # GL_RGBA16F: 4 canales float de 16 bits → rango HDR antes de tonemap.
        # Attachment.Depth: Qt añade un depth renderbuffer para que la
        # profundidad funcione durante la pasada de escena.
        fmt = QOpenGLFramebufferObjectFormat()
        fmt.setAttachment(QOpenGLFramebufferObject.Attachment.Depth)
        fmt.setTextureTarget(GL_TEXTURE_2D)
        fmt.setInternalTextureFormat(GL_RGBA16F)

        self._fbo = QOpenGLFramebufferObject(QSize(w, h), fmt)
        if not self._fbo.isValid():
            raise RuntimeError(
                "Post-process FBO inválido (GL_RGBA16F no soportado). "
                "Comprueba que el driver soporta texturas float (OpenGL 3.0+)."
            )

        self._tex = self._fbo.texture()

        # GL_LINEAR para que FXAA pueda interpolar entre texeles
        glBindTexture(GL_TEXTURE_2D, self._tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glBindTexture(GL_TEXTURE_2D, 0)

    def resize(self, w: int, h: int) -> None:
        """Recrear el FBO al cambiar el tamaño del viewport."""
        self._width  = max(1, int(w))
        self._height = max(1, int(h))
        del self._fbo
        self._create_fbo(self._width, self._height)

    # ── Quad NDC (2 triángulos que cubren toda la pantalla) ───────────────
    def _create_quad(self) -> None:
        verts = np.array([
            -1, -1,   1, -1,   1,  1,
            -1, -1,   1,  1,  -1,  1,
        ], dtype=np.float32)
        self._vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, False, 8, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

    # ── Ciclo de render ───────────────────────────────────────────────────
    def begin(self) -> None:
        """Bind el FBO offscreen; todo lo que se dibuje después va aquí."""
        self._fbo.bind()

    def end(self) -> None:
        """Aplica los efectos y vuelca al framebuffer por defecto de Qt."""
        QOpenGLFramebufferObject.bindDefault()
        glViewport(0, 0, self._width, self._height)

        glDisable(GL_DEPTH_TEST)

        self._shader.use()
        self._shader.set_int  ("uScene",             0)
        self._shader.set_vec2 ("uTexelSize",
                               np.array([1.0 / self._width,
                                         1.0 / self._height], dtype=np.float32))
        self._shader.set_int  ("uTonemap",           int(self.tonemap_enabled))
        self._shader.set_float("uExposure",          float(self.exposure))
        self._shader.set_int  ("uVignette",          int(self.vignette_enabled))
        self._shader.set_float("uVignetteIntensity", float(self.vignette_intensity))
        self._shader.set_int  ("uFXAA",              int(self.fxaa_enabled))

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self._tex)

        glBindVertexArray(self._vao)
        glDrawArrays(GL_TRIANGLES, 0, 6)
        glBindVertexArray(0)

        glEnable(GL_DEPTH_TEST)

    def delete(self) -> None:
        del self._fbo
