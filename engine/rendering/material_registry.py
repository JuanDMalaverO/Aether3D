"""
MaterialRegistry — carga y cachea materiales desde archivos JSON.
También cachea texturas cargadas (path → GL texture ID).
"""
import os
import json
import numpy as np
from OpenGL.GL import *
from engine.components.material import Material


class MaterialRegistry:
    def __init__(self):
        self._materials: dict[str, Material] = {}
        self._textures:  dict[str, int]      = {}   # path → GL tex ID

    def get_or_create(self, name: str, albedo=None) -> Material:
        """Devuelve el material por nombre, o crea uno con albedo dado."""
        if name in self._materials:
            return self._materials[name]
        m = Material(name=name)
        if albedo is not None:
            m.albedo = np.array(albedo, np.float32)
        self._materials[name] = m
        return m

    def load_from_json(self, path: str) -> 'Material | None':
        """Carga un material desde un archivo JSON y lo cachea por nombre."""
        try:
            with open(path, encoding='utf-8') as f:
                d = json.load(f)
            name = d.get("name", os.path.splitext(os.path.basename(path))[0])
            m = Material(
                name=name,
                albedo=np.array(d.get("albedo", [0.8, 0.8, 0.8]), np.float32),
                metallic=float(d.get("metallic", 0.0)),
                roughness=float(d.get("roughness", 0.5)),
                emission=np.array(d.get("emission", [0.0, 0.0, 0.0]), np.float32),
                emission_strength=float(d.get("emission_strength", 0.0)),
                albedo_map=d.get("albedo_map", ""),
                metallic_roughness_map=d.get("metallic_roughness_map", ""),
                normal_map=d.get("normal_map", ""),
                ao_map=d.get("ao_map", ""),
            )
            self._materials[name] = m
            return m
        except Exception as e:
            print(f"[MaterialRegistry] Error cargando {path}: {e}")
            return None

    def load_dir(self, directory: str) -> None:
        """Carga todos los .json de un directorio."""
        if not os.path.isdir(directory):
            return
        for fn in os.listdir(directory):
            if fn.endswith(".json"):
                self.load_from_json(os.path.join(directory, fn))

    def get_texture(self, path: str) -> int:
        """Carga y cachea una textura GL. Devuelve 0 si no existe."""
        if not path:
            return 0
        if path in self._textures:
            return self._textures[path]
        if not os.path.isfile(path):
            return 0
        try:
            from PIL import Image
            img = Image.open(path).convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            data = np.array(img, dtype=np.uint8)
            tex = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height,
                         0, GL_RGBA, GL_UNSIGNED_BYTE, data)
            glGenerateMipmap(GL_TEXTURE_2D)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glBindTexture(GL_TEXTURE_2D, 0)
            self._textures[path] = int(tex)
            return int(tex)
        except Exception as e:
            print(f"[MaterialRegistry] Error cargando textura {path}: {e}")
            return 0

    @property
    def materials(self) -> dict:
        return dict(self._materials)
