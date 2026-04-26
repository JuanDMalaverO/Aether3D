"""
MainWindow - Ventana principal del editor.
Carga la UI desde main_window.ui (Qt Designer) y conecta la lógica.
"""
import os
import json
import numpy as np
from PyQt6 import uic
from PyQt6.QtWidgets import (
    QMainWindow, QListWidget, QTextEdit, QWidget, QVBoxLayout,
    QListWidgetItem, QTreeWidgetItem, QFileDialog, QMessageBox, QToolBar,
    QLabel, QComboBox,
)
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtCore import Qt

from engine.ecs import World
from engine.components import Transform, MeshRenderer, Rigidbody, Collider, Script, Camera
from editor.viewport import Viewport
from editor.inspector import InspectorWidget
from editor.hierarchy_tree import HierarchyTree


UI_FILE = os.path.join(os.path.dirname(__file__), "main_window.ui")


class MainWindow(QMainWindow):
    def __init__(self, world: World):
        super().__init__()
        self.world = world

        uic.loadUi(UI_FILE, self)

        self._current_scene_path: str | None = None   # ruta del mundo activo

        self._setup_viewport()
        self._setup_inspector()
        self._setup_hierarchy_tree()
        self._setup_gizmo_toolbar()
        self._connect_actions()
        self._populate_hierarchy_tree()
        self._log_welcome()
        self.setWindowTitle("Aether3D — Editor  ·  Juan Malaver")
        self.statusBar().showMessage(
            "Aether3D v1.0  ·  Desarrollado por Juan Malaver  ·  PBR · Física · Scripting · ECS"
        )

    # ---------- Inyección del viewport OpenGL ----------
    def _setup_viewport(self):
        self.viewport = Viewport(self.world, self)
        layout = self.viewportContainer.layout()
        if layout is None:
            layout = QVBoxLayout(self.viewportContainer)
            layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.viewport)
        # Picking: el viewport emite entity_picked cuando el usuario hace clic
        self.viewport.entity_picked.connect(self._on_entity_picked)
        self.viewport.delete_entity_requested.connect(self._on_delete_entity)

    # ---------- Toolbar gizmos ----------
    def _setup_gizmo_toolbar(self):
        _TB = (
            "QToolBar {"
            "  background: #0a0a0e;"
            "  border-bottom: 1px solid #1c1c28;"
            "  spacing: 1px;"
            "  padding: 3px 6px;"
            "}"
            "QToolBar::separator {"
            "  background: #1e1e2c;"
            "  width: 1px;"
            "  margin: 4px 6px;"
            "}"
            "QToolButton {"
            "  color: #8888aa;"
            "  background: transparent;"
            "  border: 1px solid transparent;"
            "  border-radius: 5px;"
            "  padding: 4px 12px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "  min-width: 54px;"
            "}"
            "QToolButton:checked {"
            "  background: #6c63ff22;"
            "  border-color: #6c63ff66;"
            "  color: #c4bcff;"
            "}"
            "QToolButton:hover:!checked {"
            "  background: #1e1e2c;"
            "  border-color: #2a2a3a;"
            "  color: #b0b0cc;"
            "}"
            "QToolButton:pressed { background: #6c63ff33; }"
            "QToolButton:disabled { color: #3a3a50; }"
        )
        _COMBO = (
            "QComboBox {"
            "  background: #13131c;"
            "  color: #9090b8;"
            "  border: 1px solid #2a2a3c;"
            "  border-radius: 5px;"
            "  padding: 3px 8px;"
            "  font-size: 11px;"
            "}"
            "QComboBox:hover { border-color: #6c63ff66; color: #b0b0cc; }"
            "QComboBox::drop-down { border: none; width: 18px; }"
            "QComboBox::down-arrow { width: 0; height: 0; }"
            "QComboBox QAbstractItemView {"
            "  background: #13131c;"
            "  color: #b0b0cc;"
            "  border: 1px solid #2a2a3c;"
            "  selection-background-color: #6c63ff33;"
            "  outline: none;"
            "}"
        )
        _LBL = "color: #4a4a6a; padding: 0 4px; font-size: 11px;"

        tb = QToolBar("Modos", self)
        tb.setMovable(False)
        tb.setStyleSheet(_TB)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        group = QActionGroup(self)
        group.setExclusive(True)
        for key, label, tip in [
            ("select",    "Select",   "Seleccionar entidades con clic"),
            ("translate", "Move",     "Mover — arrastra un eje"),
            ("rotate",    "Rotate",   "Rotar — arrastra un anillo"),
            ("scale",     "Scale",    "Escalar — arrastra un eje"),
        ]:
            act = QAction(label, self)
            act.setCheckable(True)
            act.setToolTip(tip)
            act.setChecked(key == "select")
            act.triggered.connect(lambda checked, k=key: self.viewport.set_gizmo_mode(k))
            group.addAction(act)
            tb.addAction(act)

        # ── Añadir primitivas ──────────────────────────────────────────
        tb.addSeparator()
        for mesh_name, label, tip in [
            ("cube",   "+ Cubo",   "Añadir cubo a la escena"),
            ("sphere", "+ Esfera", "Añadir esfera a la escena"),
            ("plane",  "+ Plano",  "Añadir plano a la escena"),
        ]:
            act = QAction(label, self)
            act.setToolTip(tip)
            act.triggered.connect(lambda checked, m=mesh_name: self._on_add_primitive(m))
            tb.addAction(act)

        cam_act = QAction("+ Cámara", self)
        cam_act.setToolTip("Añadir entidad Camera a la escena")
        cam_act.triggered.connect(self._on_add_camera)
        tb.addAction(cam_act)

        # ── Selector de velocidad WASD ────────────────────────────────
        tb.addSeparator()
        vel_lbl = QLabel("  Vel")
        vel_lbl.setStyleSheet(_LBL)
        tb.addWidget(vel_lbl)

        _speeds = [("0.25×", 0.25), ("0.5×", 0.5), ("1×", 1.0),
                   ("2×", 2.0), ("5×", 5.0), ("10×", 10.0)]
        speed_combo = QComboBox()
        speed_combo.addItems([s for s, _ in _speeds])
        speed_combo.setCurrentIndex(2)
        speed_combo.setToolTip("Velocidad de movimiento WASD / Shift / Ctrl")
        speed_combo.setStyleSheet(_COMBO + "QComboBox { min-width: 54px; }")
        speed_combo.currentIndexChanged.connect(
            lambda idx: setattr(self.viewport, '_camera_speed', _speeds[idx][1])
        )
        tb.addWidget(speed_combo)

        # ── Previsualizar desde cámara ────────────────────────────────
        tb.addSeparator()
        cam_lbl = QLabel("  Vista")
        cam_lbl.setStyleSheet(_LBL)
        tb.addWidget(cam_lbl)
        self._cam_combo = QComboBox()
        self._cam_combo.setToolTip("Previsualizar desde esta cámara (solo editor)")
        self._cam_combo.setStyleSheet(_COMBO + "QComboBox { min-width: 110px; }")
        self._cam_combo.addItem("Cámara editor", userData=None)
        self._cam_combo.currentIndexChanged.connect(self._on_camera_combo_changed)
        tb.addWidget(self._cam_combo)

        # ── Play / Pause / Stop ──────────────────────────────────────
        tb.addSeparator()
        self._play_act  = QAction("▶", self)
        self._pause_act = QAction("⏸", self)
        self._stop_act  = QAction("⏹", self)
        self._play_act .setToolTip("Play — iniciar modo juego")
        self._pause_act.setToolTip("Pausa — congelar simulación")
        self._stop_act .setToolTip("Stop — detener y restaurar escena")
        self._pause_act.setEnabled(False)
        self._stop_act .setEnabled(False)
        self._play_act .triggered.connect(self._on_play)
        self._pause_act.triggered.connect(self._on_pause)
        self._stop_act .triggered.connect(self._on_stop)
        for act in (self._play_act, self._pause_act, self._stop_act):
            tb.addAction(act)

    # ---------- Inspector ----------
    def _setup_inspector(self):
        from PyQt6.QtCore import Qt as _Qt
        self.inspector = InspectorWidget(self.world, self.viewport)
        self.inspectorScroll.setWidget(self.inspector)
        # Si el dock se estrecha más que el minimumWidth del inspector,
        # aparece scrollbar horizontal en lugar de que el contenido se salga.
        self.inspectorScroll.setHorizontalScrollBarPolicy(
            _Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.inspectorScroll.setVerticalScrollBarPolicy(
            _Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

    # ---------- Jerarquía (árbol con drag-drop) ----------
    def _setup_hierarchy_tree(self):
        """Sustituye el QListWidget del .ui por un HierarchyTree."""
        self.hierarchyTree = HierarchyTree()

        # Reemplazamos el widget en el mismo layout
        parent_widget = self.hierarchyList.parentWidget()
        layout = parent_widget.layout()
        layout.replaceWidget(self.hierarchyList, self.hierarchyTree)
        self.hierarchyList.hide()

        self.hierarchyTree.currentItemChanged.connect(self._on_hierarchy_selection)
        self.hierarchyTree.reparent_requested.connect(self._on_reparent)
        self.hierarchyTree.delete_requested.connect(self._on_delete_entity)
        self.hierarchyTree.rename_requested.connect(self._on_rename_entity)

    def _populate_hierarchy_tree(self, restore_selection: int | None = None):
        """Reconstruye el árbol visual a partir de la jerarquía del mundo."""
        self.hierarchyTree.blockSignals(True)
        self.hierarchyTree.clear()

        def add_item(parent, entity_id: int) -> QTreeWidgetItem:
            name = self.world.get_entity_name(entity_id)
            item = QTreeWidgetItem([name])
            item.setData(0, Qt.ItemDataRole.UserRole, entity_id)
            if isinstance(parent, HierarchyTree):
                parent.addTopLevelItem(item)
            else:
                parent.addChild(item)
            item.setExpanded(True)
            for child_id in self.world.get_children(entity_id):
                add_item(item, child_id)
            return item

        items_by_id: dict[int, QTreeWidgetItem] = {}
        for root_id in self.world.get_root_entities():
            items_by_id[root_id] = add_item(self.hierarchyTree, root_id)

        self.hierarchyTree.blockSignals(False)

        # Restaurar selección si la entidad sigue existiendo
        target = restore_selection if restore_selection is not None else self.world.selected_entity
        if target is not None:
            self._select_tree_item(target)

        # Actualizar combo de cámaras
        if hasattr(self, '_cam_combo'):
            self.refresh_camera_combo()

    def _select_tree_item(self, entity_id: int) -> None:
        """Busca y selecciona el ítem del árbol con el entity_id dado."""
        def find(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            if item.data(0, Qt.ItemDataRole.UserRole) == entity_id:
                return item
            for i in range(item.childCount()):
                found = find(item.child(i))
                if found:
                    return found
            return None

        for i in range(self.hierarchyTree.topLevelItemCount()):
            found = find(self.hierarchyTree.topLevelItem(i))
            if found:
                self.hierarchyTree.setCurrentItem(found)
                return

    # ---------- Conexión de acciones del menú ----------
    def _connect_actions(self):
        self.actionSalir.triggered.connect(self.close)
        self.actionNuevaEscena.triggered.connect(self._on_new_scene)
        self.actionAbrir.triggered.connect(self._on_open_scene)
        self.actionGuardar.triggered.connect(self._on_save_scene)
        self.actionResetCamara.triggered.connect(self._on_reset_camera)

        # Importar modelo OBJ
        self._import_action = QAction("Importar modelo (.obj)…", self)
        self._import_action.setShortcut("Ctrl+I")
        self._import_action.triggered.connect(self._on_import_obj)
        self.menuArchivo.insertSeparator(self.actionSalir)
        self.menuArchivo.insertAction(self.actionSalir, self._import_action)

        # Acerca de Aether3D
        about_act = QAction("Acerca de Aether3D…", self)
        about_act.triggered.connect(self._on_about)
        self.menuVer.addSeparator()
        self.menuVer.addAction(about_act)

        # Submenú Skybox en Ver
        self.menuVer.addSeparator()
        skybox_menu = self.menuVer.addMenu("Skybox")
        skybox_group = QActionGroup(self)
        skybox_group.setExclusive(True)
        for key, label in [
            ("none",  "Ninguno"),
            ("space", "Espacio / Nebulosa"),
            ("sky",   "Exterior / Cielo"),
        ]:
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(key == "space")
            act.triggered.connect(lambda checked, k=key: self.viewport.set_skybox(k if k != "none" else None))
            skybox_group.addAction(act)
            skybox_menu.addAction(act)

        # Submenú Post-processing en Ver
        self.menuVer.addSeparator()
        pp_menu = self.menuVer.addMenu("Post-processing")

        def _pp():
            return getattr(self.viewport, 'post_process', None)

        def _pp_act(label, default, attr):
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(default)
            def _toggle(checked, a=attr):
                pp = _pp()
                if pp:
                    setattr(pp, a, checked)
                    self.viewport.update()
            act.triggered.connect(_toggle)
            pp_menu.addAction(act)
            return act

        _pp_act("Activar Post-processing",  True,  "enabled")
        pp_menu.addSeparator()
        _pp_act("Tonemapping (ACES)",        True,  "tonemap_enabled")
        _pp_act("Viñeta",                    False, "vignette_enabled")
        _pp_act("FXAA",                      False, "fxaa_enabled")

    # ---------- Handlers ----------
    # ──────────────────────────────────────────────────────────────────
    def _on_play(self) -> None:
        st = self.viewport._game_state
        if st == "stopped":
            self.viewport.start_play()
        elif st == "paused":
            self.viewport.pause_play()   # reanudar
        self._update_play_ui(self.viewport._game_state)

    def _on_pause(self) -> None:
        self.viewport.pause_play()
        self._update_play_ui(self.viewport._game_state)

    def _on_stop(self) -> None:
        if self.viewport._game_state == "stopped":
            return
        self.viewport.stop_play()
        self._update_play_ui("stopped")
        self._populate_hierarchy_tree()
        self.inspector.set_entity(self.world.selected_entity)

    def _update_play_ui(self, state: str) -> None:
        self._play_act .setEnabled(state != "playing")
        self._pause_act.setEnabled(state == "playing")
        self._stop_act .setEnabled(state != "stopped")
        self._play_act .setText("▶ Reanudar" if state == "paused" else "▶")

        # Bloquear / desbloquear editor
        locked = state != "stopped"
        self.hierarchyTree.setEnabled(not locked)
        self.inspectorScroll.setEnabled(not locked)

        msgs = {
            "playing": ("▶ Modo juego — WASD mover · Mouse girar · Espacio saltar · Esc detener", "ok"),
            "paused":  ("⏸ Pausa — simulación congelada", "warn"),
            "stopped": ("Editor activo — escena restaurada", "info"),
        }
        txt, lvl = msgs.get(state, ("", "info"))
        if txt:
            self.log(txt, lvl)

    def refresh_camera_combo(self) -> None:
        """Actualiza el combo de cámaras con las entidades que tienen Camera en la escena."""
        self._cam_combo.blockSignals(True)
        current_eid = self._cam_combo.currentData()
        self._cam_combo.clear()
        self._cam_combo.addItem("Cámara editor", userData=None)
        for eid in self.world.all_entities():
            if self.world.get_component(eid, Camera) is not None:
                name = self.world.get_entity_name(eid)
                cam  = self.world.get_component(eid, Camera)
                label = f"{name} {'★' if cam.is_main else ''}"
                self._cam_combo.addItem(label.strip(), userData=eid)
        # Restaurar selección si sigue existiendo
        idx = 0
        for i in range(self._cam_combo.count()):
            if self._cam_combo.itemData(i) == current_eid:
                idx = i
                break
        self._cam_combo.setCurrentIndex(idx)
        self._cam_combo.blockSignals(False)
        self._on_camera_combo_changed(self._cam_combo.currentIndex())

    def _on_camera_combo_changed(self, index: int) -> None:
        eid = self._cam_combo.itemData(index)
        self.viewport._preview_camera_eid = eid
        self.viewport.update()

    def _on_rename_entity(self, entity_id: int) -> None:
        from PyQt6.QtWidgets import QInputDialog
        current = self.world.get_entity_name(entity_id)
        new_name, ok = QInputDialog.getText(
            self, "Renombrar entidad", "Nuevo nombre:", text=current)
        if ok and new_name.strip():
            self.world.set_entity_name(entity_id, new_name.strip())
            self._populate_hierarchy_tree(restore_selection=entity_id)
            self.inspector.set_entity(entity_id)   # refresca el encabezado del inspector

    def _on_delete_entity(self, entity_id: int) -> None:
        """Elimina una entidad del mundo y actualiza toda la UI."""
        name = self.world.get_entity_name(entity_id)

        # Entidad protegida: el Jugador nunca puede eliminarse
        if name == "Jugador":
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Entidad protegida",
                "«Jugador» es la entidad principal del mundo y no puede eliminarse.\n"
                "Puedes modificar sus componentes pero nunca eliminarlo.",
            )
            return

        # Limpiar estado interno de sistemas que mantienen dicts por entity_id
        ss = getattr(self.viewport, 'script_system', None)
        if ss:
            ss._instances.pop(entity_id, None)
            ss._errors.pop(entity_id, None)
            ss._started.discard(entity_id)

        ps = getattr(self.viewport, 'particle_system', None)
        if ps and entity_id in ps._states:
            ps._states[entity_id].delete()
            del ps._states[entity_id]

        self.world.destroy_entity(entity_id)

        self.inspector.set_entity(None)
        self._populate_hierarchy_tree()
        self.viewport.update()
        self.log(f"Eliminada: {name}", "info")

    def closeEvent(self, event) -> None:
        """Pide confirmación antes de salir del editor."""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Salir de Aether3D",
            "¿Seguro que quieres salir?\n\nLos cambios no guardados se perderán.",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self._on_save_scene()
            event.accept()
        elif reply == QMessageBox.StandardButton.Discard:
            event.accept()
        else:
            event.ignore()

    def _on_add_primitive(self, mesh_name: str) -> None:
        """Añade una entidad con TODOS los componentes estándar a la escena."""
        label = mesh_name.capitalize()
        eid = self.world.create_entity(label)

        # ── Transform ────────────────────────────────────────────────
        self.world.add_component(eid, Transform(
            position=np.array([0.0, 0.5, 0.0], dtype=np.float32),
        ))

        # ── MeshRenderer ─────────────────────────────────────────────
        self.world.add_component(eid, MeshRenderer(
            mesh_name=mesh_name,
            color=np.array([0.8, 0.8, 0.8], dtype=np.float32),
        ))

        # ── Rigidbody ─────────────────────────────────────────────────
        self.world.add_component(eid, Rigidbody(
            mass=1.0, restitution=0.3, friction=0.5,
            use_gravity=True, is_static=False,
        ))

        # ── Collider (forma adaptada al mesh) ─────────────────────────
        if mesh_name == "sphere":
            self.world.add_component(eid, Collider(shape="sphere", radius=0.5))
        elif mesh_name == "plane":
            self.world.add_component(eid, Collider(
                shape="aabb",
                size=np.array([10.0, 0.05, 10.0], dtype=np.float32),
            ))
        else:  # cube u otros
            self.world.add_component(eid, Collider(
                shape="aabb",
                size=np.array([1.0, 1.0, 1.0], dtype=np.float32),
            ))

        # ── Script (ruta vacía; editable desde el inspector) ──────────
        self.world.add_component(eid, Script(path=""))

        self.world.selected_entity = eid
        self._populate_hierarchy_tree()
        self._select_tree_item(eid)
        self.inspector.set_entity(eid)
        self.viewport.update()
        self.log(f"Añadido: {label}  (Transform · MeshRenderer · Rigidbody · Collider · Script)", "ok")

    def _on_add_camera(self) -> None:
        """Añade una entidad Cámara vacía (Transform + Camera + Script opcional)."""
        eid = self.world.create_entity("Camera")
        self.world.add_component(eid, Transform(
            position=np.array([0.0, 1.7, 5.0], dtype=np.float32),
        ))
        self.world.add_component(eid, Camera(fov=60.0, near=0.1, far=1000.0, is_main=False))
        self.world.add_component(eid, Script(path=""))
        self.world.selected_entity = eid
        self._populate_hierarchy_tree()
        self._select_tree_item(eid)
        self.inspector.set_entity(eid)
        self.viewport.update()
        self.log("Añadida: Camera  (Transform · Camera · Script)", "ok")

    def _on_new_scene(self) -> None:
        reply = QMessageBox.question(
            self, "Nueva escena",
            "¿Crear una escena nueva?\nLos cambios no guardados se perderán.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.world.clear_all()
        self._current_scene_path = None
        self.setWindowTitle("Aether3D — Nuevo Mundo  ·  Juan Malaver")
        self._add_default_player()
        self.inspector.set_entity(None)
        self._populate_hierarchy_tree()
        self.viewport.update()
        self.log("Nuevo mundo creado — Jugador añadido automáticamente", "ok")

    # ──────────────────────────────────────────────────────────────────
    def _on_save_scene(self) -> None:
        worlds_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '..', 'worlds')
        )
        os.makedirs(worlds_dir, exist_ok=True)

        # Si ya hay ruta guardada, guardar directo sin diálogo
        if self._current_scene_path:
            self._save_to(self._current_scene_path)
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Guardar mundo — Aether3D", worlds_dir,
            "Mundos Aether3D (*.json)"
        )
        if not filepath:
            return
        if not filepath.lower().endswith('.json'):
            filepath += '.json'
        self._current_scene_path = filepath
        self._save_to(filepath)

    def _save_to(self, filepath: str) -> None:
        from engine.scene.serializer import world_to_dict
        try:
            data = world_to_dict(self.world, self.viewport.mesh_sources)
            with open(filepath, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            name = os.path.splitext(os.path.basename(filepath))[0]
            n    = len(data["entities"])
            self.setWindowTitle(f"Aether3D — {name}  ·  Juan Malaver")
            self.log(f"Mundo guardado: {name}  ({n} entidades)  →  worlds/", "ok")
        except Exception as exc:
            self.log(f"Error al guardar: {exc}", "error")

    # ──────────────────────────────────────────────────────────────────
    def _on_open_scene(self) -> None:
        worlds_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '..', 'worlds')
        )
        os.makedirs(worlds_dir, exist_ok=True)

        filepath, _ = QFileDialog.getOpenFileName(
            self, "Cargar mundo — Aether3D", worlds_dir,
            "Mundos Aether3D (*.json);;Todos los archivos (*)"
        )
        if not filepath:
            return

        # ── Leer y validar JSON ───────────────────────────────────────
        try:
            with open(filepath, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            self.log(f"Archivo corrupto (JSON inválido): {exc}", "error")
            return
        except OSError as exc:
            self.log(f"Error al leer el archivo: {exc}", "error")
            return

        if not isinstance(data, dict):
            self.log("Formato de escena inválido: se esperaba un objeto JSON.", "error")
            return

        # ── Limpiar mundo ─────────────────────────────────────────────
        self.world.clear_all()
        self.viewport.mesh_sources.clear()

        # ── Deserializar ──────────────────────────────────────────────
        from engine.scene.serializer import world_from_dict
        known = set(self.viewport.mesh_registry.keys())
        warnings, to_import = world_from_dict(self.world, data, known)

        # ── Auto-importar meshes faltantes ────────────────────────────
        from engine.rendering.obj_loader import load_obj
        from engine.components.mesh import MeshRenderer

        for mesh_name, source in to_import:
            imported = False
            if source and os.path.isfile(source):
                try:
                    self.viewport.makeCurrent()
                    try:
                        mesh = load_obj(source)
                    finally:
                        self.viewport.doneCurrent()
                    self.viewport.mesh_registry[mesh_name] = mesh
                    self.viewport.mesh_sources[mesh_name] = source
                    # Corregir los MeshRenderer que usaban placeholder "cube"
                    for eid, mr in self.world.get_components_of_type(MeshRenderer).items():
                        if getattr(mr, '_pending_mesh', None) == mesh_name:
                            mr.mesh_name = mesh_name
                            mr._pending_mesh = None
                    self.log(f"Auto-importado: {mesh_name}", "ok")
                    imported = True
                except Exception as exc:
                    warnings.append(f"No se pudo auto-importar '{mesh_name}': {exc}")

            if not imported:
                hint = f" (ruta esperada: {source})" if source else ""
                warnings.append(
                    f"Mesh '{mesh_name}' no disponible{hint}; "
                    "las entidades que lo usan muestran 'cube' como sustituto."
                )

        # ── Reportar advertencias ─────────────────────────────────────
        for w in warnings:
            self.log(w, "warn")

        n = len(self.world.all_entities())
        name = os.path.splitext(os.path.basename(filepath))[0]
        self.log(f"Mundo cargado: {name}  ({n} entidades)", "ok")
        self._current_scene_path = filepath
        self.setWindowTitle(f"Aether3D — {name}  ·  Juan Malaver")

        # ── Refrescar UI ──────────────────────────────────────────────
        self._populate_hierarchy_tree()
        self.inspector.set_entity(None)
        self.viewport.update()

    def _add_default_player(self) -> None:
        """Añade el Jugador si no existe (entidad protegida, siempre presente)."""
        for eid in self.world.all_entities():
            if self.world.get_entity_name(eid) == "Jugador":
                return   # ya existe
        import numpy as np
        from engine.components import (
            Transform, MeshRenderer, Rigidbody, Collider, Material
        )
        eid = self.world.create_entity("Jugador")
        self.world.add_component(eid, Transform(
            position=np.array([0.0, 1.1, 6.0], dtype=np.float32),
        ))
        self.world.add_component(eid, MeshRenderer(
            mesh_name="capsule",
            color=np.array([0.55, 0.78, 1.0], dtype=np.float32),
        ))
        self.world.add_component(eid, Material(
            name="Jugador",
            albedo=np.array([0.55, 0.78, 1.0], np.float32),
            metallic=0.0, roughness=0.5,
        ))
        self.world.add_component(eid, Rigidbody(
            mass=75.0, restitution=0.0, friction=0.8,
            use_gravity=True, is_static=False,
        ))
        self.world.add_component(eid, Collider(shape="sphere", radius=0.38))

    def _on_open_scene_path(self, filepath: str) -> None:
        """Carga un mundo directamente desde ruta (llamado desde StartScreen)."""
        try:
            with open(filepath, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception as exc:
            self.log(f"Error al cargar mundo: {exc}", "error")
            return
        self.world.clear_all()
        self.viewport.mesh_sources.clear()
        from engine.scene.serializer import world_from_dict
        known = set(self.viewport.mesh_registry.keys()) if hasattr(self.viewport, 'mesh_registry') else set()
        warnings, _ = world_from_dict(self.world, data, known)
        for w in warnings:
            self.log(w, "warn")
        # Garantizar que siempre haya Jugador
        self._add_default_player()
        n    = len(self.world.all_entities())
        name = os.path.splitext(os.path.basename(filepath))[0]
        self._current_scene_path = filepath
        self.setWindowTitle(f"Aether3D — {name}  ·  Juan Malaver")
        self.log(f"Mundo cargado: {name}  ({n} entidades)", "ok")
        self._populate_hierarchy_tree()
        self.inspector.set_entity(None)
        self.viewport.update()

    def _on_about(self) -> None:
        from editor.about_dialog import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec()

    def _on_reset_camera(self):
        import numpy as np
        self.viewport.camera.target = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.viewport.camera.distance = 8.0
        self.viewport.camera.yaw = 45.0
        self.viewport.camera.pitch = 30.0
        self.viewport.update()
        self.log("Cámara reseteada", "info")

    def _on_hierarchy_selection(self, current, previous):
        if current is None:
            self.world.selected_entity = None
            self.inspector.set_entity(None)
            self.viewport.update()
            return
        entity_id = current.data(0, Qt.ItemDataRole.UserRole)
        if entity_id is None:
            return
        self.world.selected_entity = entity_id
        self.inspector.set_entity(entity_id)
        self.viewport.update()
        self.log(f"Seleccionada: {self.world.get_entity_name(entity_id)}", "info")

    def _on_entity_picked(self, entity_id) -> None:
        """Callback del viewport cuando el usuario hace clic izquierdo."""
        self.inspector.set_entity(entity_id)
        # Sincronizar el árbol de jerarquía sin disparar _on_hierarchy_selection
        self.hierarchyTree.blockSignals(True)
        if entity_id is not None:
            self._select_tree_item(entity_id)
            self.log(f"Seleccionada: {self.world.get_entity_name(entity_id)}", "info")
        else:
            self.hierarchyTree.clearSelection()
        self.hierarchyTree.blockSignals(False)

    def _on_import_obj(self) -> None:
        start_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '..', 'assets', 'models')
        )
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Importar modelo OBJ", start_dir, "Modelos OBJ (*.obj)"
        )
        if not filepath:
            return

        base = os.path.splitext(os.path.basename(filepath))[0]
        # Si el nombre ya existe en el registro, añadir sufijo numérico
        mesh_name = base
        n = 1
        while mesh_name in self.viewport.mesh_registry:
            mesh_name = f"{base}_{n}"
            n += 1

        try:
            from engine.rendering.obj_loader import load_obj
            # Mesh.__init__ llama a OpenGL → necesitamos el contexto activo
            self.viewport.makeCurrent()
            try:
                mesh = load_obj(filepath)
            finally:
                self.viewport.doneCurrent()

            self.viewport.mesh_registry[mesh_name] = mesh
            self.viewport.mesh_sources[mesh_name] = filepath

            # Tamaño del collider AABB deducido del bounding box real del mesh
            aabb_size = (mesh.aabb_max - mesh.aabb_min).astype(np.float32)
            aabb_size = np.maximum(aabb_size, np.array([0.1, 0.1, 0.1], np.float32))

            entity_id = self.world.create_entity(mesh_name)

            # ── Transform ──────────────────────────────────────────────
            self.world.add_component(entity_id, Transform(
                position=np.array([0.0, 0.5, 0.0], dtype=np.float32),
            ))

            # ── MeshRenderer ───────────────────────────────────────────
            self.world.add_component(entity_id, MeshRenderer(
                mesh_name=mesh_name,
                color=np.array([0.8, 0.8, 0.8], dtype=np.float32),
            ))

            # ── Material PBR ───────────────────────────────────────────
            from engine.components import Material
            self.world.add_component(entity_id, Material(
                name=mesh_name,
                albedo=np.array([0.8, 0.8, 0.8], np.float32),
                metallic=0.0,
                roughness=0.5,
            ))

            # ── Rigidbody ──────────────────────────────────────────────
            self.world.add_component(entity_id, Rigidbody(
                mass=1.0, restitution=0.3, friction=0.5,
                use_gravity=True, is_static=False,
            ))

            # ── Collider (AABB real del mesh) ──────────────────────────
            self.world.add_component(entity_id, Collider(
                shape="aabb",
                size=aabb_size,
            ))

            # ── Script (ruta vacía, editable desde el inspector) ───────
            self.world.add_component(entity_id, Script(path=""))

            self._populate_hierarchy_tree()
            self.world.selected_entity = entity_id
            self._select_tree_item(entity_id)
            self.inspector.set_entity(entity_id)
            self.viewport.update()
            tris = mesh.vertex_count // 3
            self.log(
                f"Importado: {mesh_name}  ({tris} triángulos)"
                f"  ·  Transform · MeshRenderer · Material · Rigidbody · Collider · Script",
                "ok"
            )

        except Exception as exc:
            self.log(f"Error importando '{base}': {exc}", "error")

    def _on_reparent(self, child_id: int, parent_id) -> None:
        child_name = self.world.get_entity_name(child_id)
        self.world.set_parent(child_id, parent_id)
        if parent_id is None:
            self.log(f"{child_name} → raíz", "info")
        else:
            parent_name = self.world.get_entity_name(parent_id)
            self.log(f"{child_name} → hijo de {parent_name}", "info")
        self._populate_hierarchy_tree()
        self.viewport.update()

    # ---------- Consola ----------
    def _log_welcome(self):
        self.log("AETHER3D — Motor 3D desarrollado íntegramente por Juan Malaver", "ok")
        self.log("Pipeline PBR · ECS · Física · Scripting · Partículas GPU · Cámaras múltiples", "muted")
        self.log("Jerarquía: arrastra un ítem sobre otro para parentear · clic derecho para opciones", "muted")
        self.log("Viewport: MMB arrastrar = orbitar · Shift+MMB = pan · Scroll = zoom · WASD = volar", "muted")

    def log(self, message: str, level: str = "info"):
        colors = {
            "info":  "#6c84d4",
            "ok":    "#4ade80",
            "warn":  "#fbbf24",
            "error": "#f87171",
            "muted": "#3a3a58",
        }
        color = colors.get(level, "#9090b0")
        self.consoleOutput.append(
            f"<span style='color:{color}; font-family: Consolas, monospace;'>{message}</span>"
        )
