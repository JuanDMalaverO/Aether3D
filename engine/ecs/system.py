"""
Clase base para sistemas del ECS.
Los sistemas contienen la lógica que opera sobre componentes.
"""
from abc import ABC, abstractmethod
from engine.ecs.world import World


class System(ABC):
    def __init__(self, world: World):
        self.world = world

    @abstractmethod
    def update(self, dt: float) -> None:
        """Llamado cada frame con el delta time en segundos."""
        ...
