"""
BaseScript — interfaz base que todos los scripts de usuario deben implementar.

Cada script que el usuario cree debe:
  1. Importar BaseScript: from engine.scripting import BaseScript
  2. Crear una clase que herede de ella
  3. Sobreescribir los métodos que necesite

El ScriptSystem descubre automáticamente la clase por introspección.
"""


class BaseScript:
    """Ciclo de vida de un script de entidad."""

    def on_start(self, entity: int, world) -> None:
        """Llamado una vez al entrar en modo juego.

        Args:
            entity: ID de la entidad a la que está asignado este script.
            world:  Instancia del World ECS.
        """

    def on_update(self, entity: int, world, dt: float) -> None:
        """Llamado cada frame mientras está en modo juego.

        Args:
            entity: ID de la entidad.
            world:  Instancia del World ECS.
            dt:     Segundos transcurridos desde el frame anterior.
        """

    def on_collision(self, entity: int, other_entity: int, world) -> None:
        """Llamado cuando esta entidad colisiona con otra.

        Args:
            entity:       ID de esta entidad.
            other_entity: ID de la entidad con la que colisionó.
            world:        Instancia del World ECS.
        """
