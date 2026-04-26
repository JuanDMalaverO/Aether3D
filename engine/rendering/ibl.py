"""
IBL — Precomputa irradiance cubemap desde las imágenes de skybox en CPU.
No usa FBO para evitar problemas de extensiones PyOpenGL en Windows.
El prefiltered env map usa el skybox con glGenerateMipmap (aproximación).
"""
import os
import numpy as np
from OpenGL.GL import *

_GL_FACES = [
    GL_TEXTURE_CUBE_MAP_POSITIVE_X, GL_TEXTURE_CUBE_MAP_NEGATIVE_X,
    GL_TEXTURE_CUBE_MAP_POSITIVE_Y, GL_TEXTURE_CUBE_MAP_NEGATIVE_Y,
    GL_TEXTURE_CUBE_MAP_POSITIVE_Z, GL_TEXTURE_CUBE_MAP_NEGATIVE_Z,
]


class IBL:
    def __init__(self):
        self.irradiance_tex = 0
        self.enabled = False

    def compute_from_face_dir(self, face_dir: str, size: int = 32) -> None:
        """Carga las caras del skybox desde disco y computa la irradiance en CPU."""
        from PIL import Image
        face_keys = ['px', 'nx', 'py', 'ny', 'pz', 'nz']
        faces = []
        for key in face_keys:
            path = os.path.join(face_dir, f'{key}.png')
            if not os.path.isfile(path):
                print(f"[IBL] Cara no encontrada: {path}")
                return
            img = Image.open(path).convert('RGB').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            faces.append(np.array(img, dtype=np.float32) / 255.0)

        print(f"[IBL] Computando irradiance cubemap ({size}x{size} por cara, 256 muestras)...")
        irr = self._convolve_irradiance(faces, size)
        # Limpiar textura anterior si existe
        if self.irradiance_tex:
            glDeleteTextures(1, [self.irradiance_tex])
            self.irradiance_tex = 0
        self.irradiance_tex = self._upload_cubemap_f32(irr)
        self.enabled = True
        print(f"[IBL] Irradiance cubemap lista (tex={self.irradiance_tex})")

    # ── Interno ──────────────────────────────────────────────────────────
    def _sample_cubemap(self, faces, dirs):
        """
        Muestrea un cubemap desde un lote de vectores unitarios de dirección.
        dirs: (N, 3) float32
        Devuelve (N, 3) float32 valores RGB
        """
        N = dirs.shape[0]
        result = np.zeros((N, 3), np.float32)
        x, y, z = dirs[:, 0], dirs[:, 1], dirs[:, 2]
        ax, ay, az = np.abs(x), np.abs(y), np.abs(z)

        # Para cada una de las 6 caras: máscara, sc, tc, ma
        specs = [
            # +X
            (lambda x,y,z,ax,ay,az: (ax>=ay) & (ax>=az) & (x>0),
             lambda x,y,z,ax,ay,az: -z, lambda x,y,z,ax,ay,az: -y, lambda x,y,z,ax,ay,az: ax),
            # -X
            (lambda x,y,z,ax,ay,az: (ax>=ay) & (ax>=az) & (x<=0),
             lambda x,y,z,ax,ay,az:  z, lambda x,y,z,ax,ay,az: -y, lambda x,y,z,ax,ay,az: ax),
            # +Y
            (lambda x,y,z,ax,ay,az: (ay>ax) & (ay>=az) & (y>0),
             lambda x,y,z,ax,ay,az:  x, lambda x,y,z,ax,ay,az:  z, lambda x,y,z,ax,ay,az: ay),
            # -Y
            (lambda x,y,z,ax,ay,az: (ay>ax) & (ay>=az) & (y<=0),
             lambda x,y,z,ax,ay,az:  x, lambda x,y,z,ax,ay,az: -z, lambda x,y,z,ax,ay,az: ay),
            # +Z
            (lambda x,y,z,ax,ay,az: (az>ax) & (az>ay) & (z>0),
             lambda x,y,z,ax,ay,az:  x, lambda x,y,z,ax,ay,az: -y, lambda x,y,z,ax,ay,az: az),
            # -Z
            (lambda x,y,z,ax,ay,az: (az>ax) & (az>ay) & (z<=0),
             lambda x,y,z,ax,ay,az: -x, lambda x,y,z,ax,ay,az: -y, lambda x,y,z,ax,ay,az: az),
        ]

        for fi, (mf, sf, tf, maf) in enumerate(specs):
            mask = mf(x, y, z, ax, ay, az)
            if not mask.any():
                continue
            ma = maf(x[mask], y[mask], z[mask], ax[mask], ay[mask], az[mask])
            sc = sf(x[mask], y[mask], z[mask], ax[mask], ay[mask], az[mask])
            tc = tf(x[mask], y[mask], z[mask], ax[mask], ay[mask], az[mask])
            u = np.clip(0.5 * (sc / (ma + 1e-8) + 1.0), 0, 1)
            v = np.clip(0.5 * (tc / (ma + 1e-8) + 1.0), 0, 1)
            img = faces[fi]
            H, W = img.shape[:2]
            px = u * (W - 1)
            py = v * (H - 1)
            x0 = np.clip(px.astype(np.int32), 0, W - 2)
            y0 = np.clip(py.astype(np.int32), 0, H - 2)
            fx = (px - x0)[:, None]
            fy = (py - y0)[:, None]
            c00 = img[y0, x0]
            c10 = img[y0, x0 + 1]
            c01 = img[y0 + 1, x0]
            c11 = img[y0 + 1, x0 + 1]
            result[mask] = c00*(1-fx)*(1-fy) + c10*fx*(1-fy) + c01*(1-fx)*fy + c11*fx*fy

        return result

    def _convolve_irradiance(self, faces, size: int):
        """
        Convuelve el entorno para obtener irradiance difusa por cara del cubemap.
        Devuelve lista de 6 arrays numpy (size x size x 3 float32).
        """
        PI = np.pi
        N_SAMPLES = 256  # muestras de integración por texel de salida

        # Precalcular muestras uniformes de hemisferio en coords esféricas
        rng = np.random.default_rng(42)
        phi   = rng.uniform(0, 2*PI, N_SAMPLES).astype(np.float32)
        theta = np.arccos(1 - rng.uniform(0, 1, N_SAMPLES).astype(np.float32))  # cos-ponderado
        # Convertir a cartesiano (hemisferio local, Z=arriba)
        h_dirs = np.stack([
            np.sin(theta)*np.cos(phi),
            np.sin(theta)*np.sin(phi),
            np.cos(theta),
        ], axis=1)  # (N_SAMPLES, 3)

        # Configuración de ejes por cara: (adelante, derecha, arriba) en espacio mundo
        face_axes = [
            (np.array([1,0,0]), np.array([0,0,-1]), np.array([0,-1,0])),  # +X
            (np.array([-1,0,0]),np.array([0,0,1]), np.array([0,-1,0])),   # -X
            (np.array([0,1,0]), np.array([1,0,0]), np.array([0,0,1])),    # +Y
            (np.array([0,-1,0]),np.array([1,0,0]), np.array([0,0,-1])),   # -Y
            (np.array([0,0,1]), np.array([1,0,0]), np.array([0,-1,0])),   # +Z
            (np.array([0,0,-1]),np.array([-1,0,0]),np.array([0,-1,0])),   # -Z
        ]

        output_faces = []
        for fwd, rgt, up in face_axes:
            face_out = np.zeros((size, size, 3), np.float32)
            for row in range(size):
                for col in range(size):
                    u = (col + 0.5) / size * 2 - 1  # -1..1
                    v = (row + 0.5) / size * 2 - 1  # -1..1
                    N = (fwd + u * rgt + v * up).astype(np.float32)
                    n = np.linalg.norm(N)
                    if n < 1e-8:
                        continue
                    N /= n

                    # Construir frame tangente alrededor de N
                    world_up = np.array([0, 1, 0], np.float32)
                    if abs(N[1]) > 0.999:
                        world_up = np.array([1, 0, 0], np.float32)
                    T = np.cross(world_up, N)
                    t_len = np.linalg.norm(T)
                    if t_len < 1e-8:
                        output_faces.append(face_out)
                        continue
                    T /= t_len
                    B = np.cross(N, T)

                    # Transformar muestras del hemisferio al espacio mundo
                    world_dirs = (h_dirs[:, 0:1] * T +
                                  h_dirs[:, 1:2] * B +
                                  h_dirs[:, 2:3] * N)   # (N_SAMPLES, 3)
                    world_dirs = world_dirs / (np.linalg.norm(world_dirs, axis=1, keepdims=True) + 1e-8)

                    colors = self._sample_cubemap(faces, world_dirs)  # (N_SAMPLES, 3)
                    # Promedio cos-ponderado (muestras ya ponderadas, solo promediar)
                    face_out[row, col] = colors.mean(axis=0) * PI
            output_faces.append(face_out)
        return output_faces

    def _upload_cubemap_f32(self, face_arrays) -> int:
        """Sube 6 arrays float32 HxWx3 como un cubemap GL_RGB16F."""
        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_CUBE_MAP, tex)
        for i, arr in enumerate(face_arrays):
            h, w = arr.shape[:2]
            glTexImage2D(_GL_FACES[i], 0, GL_RGB16F, w, h, 0,
                         GL_RGB, GL_FLOAT, arr.astype(np.float32))
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE)
        glBindTexture(GL_TEXTURE_CUBE_MAP, 0)
        return int(tex)
