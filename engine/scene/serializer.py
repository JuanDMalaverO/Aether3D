"""
Serializer - Convierte el World ECS a/desde un diccionario JSON-compatible.

Formato de escena v1:
{
  "version": 1,
  "entities": [
    {
      "id": 0,
      "name": "Ground_0",
      "components": {
        "Transform": {
          "position": [0, -0.5, 0],
          "rotation": [0, 0, 0],
          "scale": [20, 0.1, 20],
          "parent": null
        },
        "MeshRenderer": {
          "mesh_name": "cube",
          "mesh_source": null,        // ruta al .obj si fue importado
          "color": [0.4, 0.4, 0.45],
          "visible": true
        }
      }
    }
  ]
}
"""
import numpy as np
from engine.ecs import World
from engine.components.transform import Transform
from engine.components.mesh import MeshRenderer
from engine.components.camera import Camera


# ──────────────────────────────────────────────────────────────────────
# Serialización
# ──────────────────────────────────────────────────────────────────────

def world_to_dict(world: World, mesh_sources: dict | None = None) -> dict:
    """Convierte el World a un dict serializable (list/float/str/None).

    mesh_sources: {mesh_name: filepath} para meshes importadas desde .obj.
    """
    entities = []
    for eid in sorted(world.all_entities()):
        entry: dict = {
            "id":   eid,
            "name": world.get_entity_name(eid),
            "components": {},
        }

        t = world.get_component(eid, Transform)
        if t is not None:
            entry["components"]["Transform"] = {
                "position": _arr(t.position),
                "rotation": _arr(t.rotation),
                "scale":    _arr(t.scale),
                "parent":   t.parent,
            }

        mr = world.get_component(eid, MeshRenderer)
        if mr is not None:
            source = (mesh_sources or {}).get(mr.mesh_name)
            entry["components"]["MeshRenderer"] = {
                "mesh_name":   mr.mesh_name,
                "mesh_source": source,
                "color":       _arr(mr.color),
                "visible":     mr.visible,
            }

        cam = world.get_component(eid, Camera)
        if cam is not None:
            entry["components"]["Camera"] = {
                "fov":        cam.fov,
                "near":       cam.near,
                "far":        cam.far,
                "projection": cam.projection,
                "ortho_size": cam.ortho_size,
                "is_main":    cam.is_main,
            }

        entities.append(entry)

    return {"version": 1, "entities": entities}


# ──────────────────────────────────────────────────────────────────────
# Deserialización
# ──────────────────────────────────────────────────────────────────────

def world_from_dict(
    world: World,
    data: dict,
    known_meshes: set | None = None,
) -> tuple[list[str], list[tuple[str, str | None]]]:
    """Carga entidades en el World desde un dict deserializado de JSON.

    El world debe estar vacío (se asume que el llamador ya llamó clear_all).

    Devuelve:
        warnings  — lista de mensajes de advertencia
        to_import — [(mesh_name, source_path|None)] meshes no encontradas
                    que el llamador debe intentar importar
    """
    warnings: list[str] = []
    to_import: list[tuple[str, str | None]] = []

    # ── Validación de estructura ──────────────────────────────────────
    version = data.get("version")
    if version != 1:
        warnings.append(f"Versión de escena desconocida: {version!r} (se esperaba 1)")

    if "entities" not in data:
        warnings.append("El archivo no contiene la clave 'entities'.")
        return warnings, to_import

    entities_raw = data["entities"]
    if not isinstance(entities_raw, list):
        warnings.append("'entities' debe ser una lista.")
        return warnings, to_import

    # ── Primera pasada: crear entidades y componentes ─────────────────
    id_map: dict[int, int] = {}   # json_id → new_world_id
    mesh_names_needed: set[str] = set()

    for e in entities_raw:
        if not isinstance(e, dict):
            warnings.append(f"Entrada de entidad inválida ignorada: {e!r}")
            continue

        json_id = e.get("id")
        stored_name = e.get("name", "Entity")
        comps = e.get("components", {})

        # Crear entidad (el nombre se sobreescribe con el almacenado)
        new_id = world.create_entity("_load")
        world.set_entity_name(new_id, stored_name)
        if json_id is not None:
            id_map[json_id] = new_id

        # Transform
        td = comps.get("Transform")
        if td is not None:
            try:
                t = Transform(
                    position=_vec3(td.get("position", [0, 0, 0])),
                    rotation=_vec3(td.get("rotation", [0, 0, 0])),
                    scale=   _vec3(td.get("scale",    [1, 1, 1])),
                    parent=  td.get("parent"),  # resolución en 2ª pasada
                )
                world.add_component(new_id, t)
            except Exception as exc:
                warnings.append(f"Entidad '{stored_name}': Transform inválido — {exc}")

        # MeshRenderer
        md = comps.get("MeshRenderer")
        if md is not None:
            try:
                mesh_name = str(md.get("mesh_name", "cube"))
                mesh_source = md.get("mesh_source")  # str o None
                color = _vec3(md.get("color", [0.8, 0.8, 0.8]))
                visible = bool(md.get("visible", True))

                if known_meshes is not None and mesh_name not in known_meshes:
                    mesh_names_needed.add(mesh_name)
                    # Aplazamos la resolución; ponemos "cube" como placeholder
                    # que se corrige si el auto-import tiene éxito
                    _store_pending_source(mesh_name, mesh_source, to_import)
                    mesh_name_actual = "cube"
                else:
                    mesh_name_actual = mesh_name

                mr = MeshRenderer(
                    mesh_name=mesh_name_actual,
                    color=color,
                    visible=visible,
                )
                # Guardamos el nombre original para corregirlo tras auto-import
                mr._pending_mesh = mesh_name if mesh_name != mesh_name_actual else None
                world.add_component(new_id, mr)
            except Exception as exc:
                warnings.append(f"Entidad '{stored_name}': MeshRenderer inválido — {exc}")

        # Camera
        cd = comps.get("Camera")
        if cd is not None:
            try:
                world.add_component(new_id, Camera(
                    fov        = float(cd.get("fov",        60.0)),
                    near       = float(cd.get("near",       0.1)),
                    far        = float(cd.get("far",        1000.0)),
                    projection = str(cd.get("projection",   "perspective")),
                    ortho_size = float(cd.get("ortho_size", 10.0)),
                    is_main    = bool(cd.get("is_main",     True)),
                ))
            except Exception as exc:
                warnings.append(f"Entidad '{stored_name}': Camera inválida — {exc}")

    # ── Segunda pasada: resolver parent IDs ───────────────────────────
    for e in entities_raw:
        json_id = e.get("id")
        new_id = id_map.get(json_id)
        if new_id is None:
            continue
        td = e.get("components", {}).get("Transform")
        if td is None:
            continue
        parent_json = td.get("parent")
        if parent_json is None:
            continue
        parent_new = id_map.get(parent_json)
        if parent_new is None:
            warnings.append(
                f"Entidad '{world.get_entity_name(new_id)}': "
                f"padre con id {parent_json} no encontrado."
            )
            continue
        t = world.get_component(new_id, Transform)
        if t is not None:
            t.parent = parent_new

    return warnings, to_import


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _arr(a) -> list:
    """Numpy array o lista → lista de floats redondeados."""
    return [round(float(x), 6) for x in a]


def _vec3(raw) -> np.ndarray:
    """Valida y convierte a ndarray float32 de 3 elementos."""
    if not (isinstance(raw, (list, tuple)) and len(raw) == 3):
        raise ValueError(f"Se esperaba una lista de 3 números, recibido: {raw!r}")
    return np.array([float(raw[0]), float(raw[1]), float(raw[2])], dtype=np.float32)


def _store_pending_source(
    mesh_name: str,
    source: str | None,
    to_import: list,
) -> None:
    """Añade (mesh_name, source) a to_import si no está ya."""
    for existing_name, _ in to_import:
        if existing_name == mesh_name:
            return
    to_import.append((mesh_name, source))
