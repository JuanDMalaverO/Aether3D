"""
ScriptSystem — carga, instancia y ejecuta scripts de usuario por entidad.

Ciclo de vida:
  start_play()  → carga todos los scripts y llama on_start
  update(dt)    → llama on_update + procesa colisiones pendientes
  stop_play()   → limpia estado de ejecución (instancias permanecen para mostrar estado)

El sistema es tolerante a fallos: un error en un script no detiene los demás.
"""
import os
import sys
import inspect
import importlib.util
import traceback

from engine.ecs.system import System
from engine.components.script import Script
from engine.scripting.base_script import BaseScript


class ScriptSystem(System):
    """Gestiona el ciclo de vida de todos los scripts de entidades."""

    def __init__(self, world):
        super().__init__(world)
        self._instances: dict[int, BaseScript] = {}   # eid → instancia
        self._errors:    dict[int, str]        = {}   # eid → mensaje de error
        self._started:   set[int]              = set()
        self._pending_collisions: list[tuple[int, int]] = []
        self.play_mode = False

    # ── Control de modo juego ──────────────────────────────────────────────
    def start_play(self) -> None:
        self.play_mode = True
        self._started.clear()
        self._pending_collisions.clear()
        self._load_all()
        for eid in list(self._instances):
            self._call(eid, 'on_start', eid, self.world)
            self._started.add(eid)

    def stop_play(self) -> None:
        self.play_mode = False
        self._started.clear()
        self._pending_collisions.clear()

    # ── Carga de scripts ───────────────────────────────────────────────────
    def _load_all(self) -> None:
        for eid, (comp,) in self.world.query(Script):
            self._load_one(eid, comp.path)

    def load_one(self, eid: int) -> None:
        """Recarga el script de una entidad concreta (llamable desde el inspector)."""
        comp = self.world.get_component(eid, Script)
        if comp:
            self._load_one(eid, comp.path)

    def _load_one(self, eid: int, path: str) -> None:
        self._instances.pop(eid, None)
        self._errors.pop(eid, None)

        if not path:
            self._errors[eid] = "Sin ruta asignada."
            return
        if not os.path.isfile(path):
            self._errors[eid] = f"Archivo no encontrado:\n{path}"
            return

        try:
            mod_name = f"_user_script_{eid}"
            # Evitar módulo cacheado si se recarga
            sys.modules.pop(mod_name, None)

            spec   = importlib.util.spec_from_file_location(mod_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)

            # Descubrir la subclase de BaseScript
            cls = None
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseScript) and obj is not BaseScript:
                    cls = obj
                    break

            if cls is None:
                self._errors[eid] = "No se encontró ninguna subclase de BaseScript."
                return

            self._instances[eid] = cls()

        except Exception:
            self._errors[eid] = traceback.format_exc()

    # ── Actualización por frame ────────────────────────────────────────────
    def update(self, dt: float) -> None:
        if not self.play_mode:
            return

        for eid, (comp,) in self.world.query(Script):
            # Cargar bajo demanda (entidades añadidas después de start_play)
            if eid not in self._instances and eid not in self._errors:
                self._load_one(eid, comp.path)

            if eid not in self._started and eid in self._instances:
                self._call(eid, 'on_start', eid, self.world)
                self._started.add(eid)

            self._call(eid, 'on_update', eid, self.world, dt)

        # Procesar callbacks de colisión
        for eid_a, eid_b in self._pending_collisions:
            self._call(eid_a, 'on_collision', eid_a, eid_b, self.world)
            self._call(eid_b, 'on_collision', eid_b, eid_a, self.world)
        self._pending_collisions.clear()

    # ── Callback de colisión (llamado por PhysicsSystem) ──────────────────
    def notify_collision(self, eid_a: int, eid_b: int) -> None:
        if self.play_mode:
            self._pending_collisions.append((eid_a, eid_b))

    # ── Estado para el inspector ───────────────────────────────────────────
    def status(self, eid: int) -> str:
        if eid in self._instances:
            return "ok"
        if eid in self._errors:
            return "error"
        return "idle"

    def error_message(self, eid: int) -> str:
        return self._errors.get(eid, "")

    # ── Llamada segura ─────────────────────────────────────────────────────
    def _call(self, eid: int, method: str, *args) -> None:
        inst = self._instances.get(eid)
        if inst is None:
            return
        fn = getattr(inst, method, None)
        if fn is None:
            return
        try:
            fn(*args)
        except Exception:
            self._errors[eid] = f"[{method}] {traceback.format_exc()}"
            print(f"[Script] Error en entidad {eid} → {method}:\n{self._errors[eid]}")
