"""
World ECS - Contenedor central del Entity Component System.

Las entidades son IDs (int). Los componentes son dataclasses que viven
indexados por tipo y por entidad. Los sistemas iteran sobre entidades
que tienen cierto set de componentes.
"""
from typing import Type, TypeVar, Iterator
from collections import defaultdict

T = TypeVar('T')


class World:
    def __init__(self):
        self._next_entity_id: int = 0
        # Diccionario: tipo_componente -> {entity_id: instancia_componente}
        self._components: dict[Type, dict[int, object]] = defaultdict(dict)
        # Set de entidades vivas
        self._entities: set[int] = set()
        # Metadata opcional por entidad (nombre, etc.)
        self._entity_names: dict[int, str] = {}
        # Entidad actualmente seleccionada en el editor (None = ninguna)
        self.selected_entity: int | None = None

    # ---------- Entidades ----------
    def create_entity(self, name: str = "Entity") -> int:
        """Crea una nueva entidad y devuelve su ID."""
        entity_id = self._next_entity_id
        self._next_entity_id += 1
        self._entities.add(entity_id)
        self._entity_names[entity_id] = f"{name}_{entity_id}"
        return entity_id

    def destroy_entity(self, entity_id: int) -> None:
        """Elimina una entidad y todos sus componentes."""
        if entity_id not in self._entities:
            return
        for comp_dict in self._components.values():
            comp_dict.pop(entity_id, None)
        self._entities.discard(entity_id)
        self._entity_names.pop(entity_id, None)
        if self.selected_entity == entity_id:
            self.selected_entity = None

    def get_entity_name(self, entity_id: int) -> str:
        return self._entity_names.get(entity_id, f"Entity_{entity_id}")

    def set_entity_name(self, entity_id: int, name: str) -> None:
        self._entity_names[entity_id] = name

    def all_entities(self) -> list[int]:
        return list(self._entities)

    def clear_all(self) -> None:
        """Elimina todas las entidades, componentes y resetea el contador."""
        self._entities.clear()
        self._components.clear()
        self._entity_names.clear()
        self._next_entity_id = 0
        self.selected_entity = None

    # ---------- Jerarquía ----------
    def get_root_entities(self) -> list[int]:
        """Entidades sin padre (Transform.parent is None, o sin Transform)."""
        from engine.components.transform import Transform
        result = []
        for eid in self._entities:
            t = self._components.get(Transform, {}).get(eid)
            if t is None or t.parent is None:
                result.append(eid)
        return sorted(result)

    def get_children(self, entity_id: int) -> list[int]:
        """Entidades cuyo Transform.parent == entity_id."""
        from engine.components.transform import Transform
        return sorted(
            eid for eid, t in self._components.get(Transform, {}).items()
            if t.parent == entity_id
        )

    def set_parent(self, child_id: int, parent_id: int | None) -> None:
        """Asigna el padre de child_id. None = raíz. Rechaza ciclos."""
        from engine.components.transform import Transform
        t = self.get_component(child_id, Transform)
        if t is None:
            return
        if parent_id is not None:
            if parent_id == child_id:
                return
            if self._would_create_cycle(child_id, parent_id):
                return
        t.parent = parent_id

    def _would_create_cycle(self, child_id: int, candidate_parent_id: int) -> bool:
        """True si parentear child_id bajo candidate_parent_id formaría un ciclo."""
        from engine.components.transform import Transform
        current = candidate_parent_id
        while current is not None:
            if current == child_id:
                return True
            t = self.get_component(current, Transform)
            if t is None:
                break
            current = t.parent
        return False

    # ---------- Componentes ----------
    def add_component(self, entity_id: int, component: object) -> None:
        """Añade un componente a una entidad."""
        if entity_id not in self._entities:
            raise ValueError(f"Entity {entity_id} no existe")
        self._components[type(component)][entity_id] = component

    def remove_component(self, entity_id: int, component_type: Type) -> None:
        self._components[component_type].pop(entity_id, None)

    def get_component(self, entity_id: int, component_type: Type[T]) -> T | None:
        """Devuelve el componente si existe, None si no."""
        return self._components[component_type].get(entity_id)

    def has_component(self, entity_id: int, component_type: Type) -> bool:
        return entity_id in self._components[component_type]

    def get_components_of_type(self, component_type: Type[T]) -> dict[int, T]:
        """Devuelve {entity_id: component} para todas las entidades con ese tipo."""
        return self._components[component_type]

    # ---------- Queries ----------
    def query(self, *component_types: Type) -> Iterator[tuple[int, tuple]]:
        """
        Itera sobre entidades que tienen TODOS los tipos de componentes pedidos.
        Uso: for entity_id, (transform, mesh) in world.query(Transform, MeshRenderer): ...
        """
        if not component_types:
            return
        # Empezamos por el tipo con menos componentes (optimización)
        sets = [set(self._components[t].keys()) for t in component_types]
        common = set.intersection(*sets) if sets else set()
        for entity_id in common:
            comps = tuple(self._components[t][entity_id] for t in component_types)
            yield entity_id, comps
