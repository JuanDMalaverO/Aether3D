"""
ParticleEmitter — componente de configuración de un sistema de partículas.

El componente almacena ÚNICAMENTE la configuración.
El estado de ejecución (partículas vivas, buffers GPU) lo mantiene
ParticleSystem internamente, mapeado por entity_id.
"""
from dataclasses import dataclass, field
import numpy as np


@dataclass
class ParticleEmitter:
    # ── Capacidad y emisión ───────────────────────────────────────────
    max_particles: int   = 200
    emission_rate: float = 30.0    # partículas/segundo (ignorado si burst=True)

    # ── Vida ──────────────────────────────────────────────────────────
    lifetime_min: float = 1.0
    lifetime_max: float = 2.0

    # ── Velocidad ─────────────────────────────────────────────────────
    speed_min: float = 1.0
    speed_max: float = 3.0

    # ── Tamaño ────────────────────────────────────────────────────────
    size_start: float = 0.3
    size_end:   float = 0.0

    # ── Color RGBA ────────────────────────────────────────────────────
    color_start: np.ndarray = field(
        default_factory=lambda: np.array([1.0, 0.9, 0.1, 1.0], np.float32))
    color_end: np.ndarray = field(
        default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0], np.float32))

    # ── Física ────────────────────────────────────────────────────────
    gravity_scale: float = 0.0    # 1.0 = gravedad normal hacia abajo

    # ── Forma del emisor ──────────────────────────────────────────────
    shape:        str   = "cone"   # "point" | "sphere" | "cone"
    shape_radius: float = 0.2      # radio del volumen del emisor
    cone_angle:   float = 25.0     # semiángulo del cono en grados

    # ── Burst (ráfaga única) ──────────────────────────────────────────
    burst:       bool = False
    burst_count: int  = 0

    # ── Estado del editor ────────────────────────────────────────────
    enabled: bool = True
