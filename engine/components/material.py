"""
Material — Componente PBR para entidades renderizables.
Usado por el PBR render path; las entidades sin Material usan Blinn-Phong básico.
"""
from dataclasses import dataclass, field
import numpy as np


@dataclass
class Material:
    name: str = "Default"
    albedo: np.ndarray = field(default_factory=lambda: np.array([0.8, 0.8, 0.8], np.float32))
    metallic: float = 0.0
    roughness: float = 0.5
    emission: np.ndarray = field(default_factory=lambda: np.zeros(3, np.float32))
    emission_strength: float = 0.0
    albedo_map: str = ""               # ruta a textura o ""
    metallic_roughness_map: str = ""   # R=metallic G=roughness (estilo glTF), o ""
    normal_map: str = ""
    ao_map: str = ""
