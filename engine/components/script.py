"""
Script — componente que enlaza una entidad con un archivo .py externo.
"""
from dataclasses import dataclass, field


@dataclass
class Script:
    path: str = ""   # ruta absoluta o relativa al archivo .py del script
