"""
InspectorWidget - Panel dinámico que muestra y edita los componentes
de la entidad seleccionada.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel,
    QDoubleSpinBox, QComboBox, QCheckBox, QPushButton, QFrame, QColorDialog,
    QSizePolicy, QLineEdit, QFileDialog, QHBoxLayout, QMenu, QInputDialog,
)
from PyQt6.QtCore import QTimer
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import numpy as np

from engine.ecs import World
from engine.components import Transform, MeshRenderer, Rigidbody, Collider, Script, ParticleEmitter, Camera, Material

_AVAILABLE_MESHES = ["cube", "sphere", "plane"]

_FRAME_STYLE = (
    "QFrame {"
    "  border: none;"
    "  border-radius: 6px;"
    "  background: #13131c;"
    "}"
)
_HEADER_STYLE = (
    "font-weight: 600;"
    "font-size: 11px;"
    "letter-spacing: 0.06em;"
    "color: #6060a0;"
    "border: none;"
    "padding-bottom: 4px;"
    "text-transform: uppercase;"
)
_LABEL_STYLE  = "color: #50506a; font-size: 11px; border: none;"
_SPIN_STYLE   = (
    "QDoubleSpinBox {"
    "  background: #0c0c14;"
    "  color: #c0c0d8;"
    "  border: 1px solid #2a2a3c;"
    "  border-radius: 4px;"
    "  padding: 2px 4px;"
    "  font-size: 11px;"
    "}"
    "QDoubleSpinBox:focus { border-color: #6c63ff66; }"
)
_COMBO_STYLE = (
    "QComboBox {"
    "  background: #0c0c14;"
    "  color: #c0c0d8;"
    "  border: 1px solid #2a2a3c;"
    "  border-radius: 4px;"
    "  padding: 2px 6px;"
    "  font-size: 11px;"
    "}"
    "QComboBox:focus { border-color: #6c63ff66; }"
    "QComboBox::drop-down { border: none; width: 14px; }"
    "QComboBox QAbstractItemView {"
    "  background: #0c0c14;"
    "  color: #c0c0d8;"
    "  border: 1px solid #2a2a3c;"
    "  selection-background-color: #6c63ff33;"
    "}"
)
_BTN_STYLE = (
    "QPushButton {"
    "  background: #1a1a28;"
    "  color: #8888b0;"
    "  border: 1px solid #2a2a3c;"
    "  border-radius: 4px;"
    "  padding: 3px 8px;"
    "  font-size: 11px;"
    "}"
    "QPushButton:hover { background: #6c63ff22; border-color: #6c63ff66; color: #c4bcff; }"
    "QPushButton:pressed { background: #6c63ff33; }"
)
_CHECK_STYLE  = "QCheckBox { color: #8888a8; border: none; font-size: 11px; }"


class InspectorWidget(QWidget):
    def __init__(self, world: World, viewport, parent=None):
        super().__init__(parent)
        self.world = world
        self.viewport = viewport
        self._entity_id: int | None = None
        self._updating = False
        # Referencias a los spinboxes del Transform para refresh rápido durante drag
        self._pos_boxes: list = []
        self._rot_boxes: list = []
        self._sca_boxes: list = []

        # Ancho mínimo: label (50) + 3 spinboxes (3×48) + espacios + márgenes ≈ 220 px.
        # El QScrollArea respeta este mínimo y agrega scrollbar horizontal si el
        # dock es más estrecho, evitando que el contenido salga del panel.
        self.setMinimumWidth(240)
        self.setStyleSheet("QWidget { background: #0f0f14; }")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(6, 8, 6, 8)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── Secciones permanentes ─────────────────────────────────────────
        self._layout.addWidget(self._make_light_section())
        self._layout.addWidget(self._sep())
        self._layout.addWidget(self._make_post_process_section())
        self._layout.addWidget(self._sep())
        # Número de widgets permanentes (se excluyen del clear dinámico)
        self._perm_count = self._layout.count()

        # ── Contenido dinámico (entidad seleccionada) ─────────────────────
        self._placeholder = QLabel("Selecciona una entidad\npara ver sus componentes")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            "color: #30304a; padding: 32px 16px; border: none;"
            "font-size: 12px; letter-spacing: 0.02em;"
        )
        self._layout.addWidget(self._placeholder)

    # ------------------------------------------------------------------ #
    def set_entity(self, entity_id: int | None) -> None:
        self._entity_id = entity_id
        self._rebuild()

    def _rebuild(self) -> None:
        self._updating = True
        try:
            self._clear_layout()
            eid = self._entity_id

            if eid is None:
                self._placeholder.show()
                self._layout.addWidget(self._placeholder)
                return

            self._placeholder.hide()

            # ── Encabezado: nombre de la entidad con menú de renombrado ──
            self._layout.addWidget(self._make_entity_header(eid))

            transform = self.world.get_component(eid, Transform)
            if transform is not None:
                self._layout.addWidget(self._make_transform_section(transform))

            mesh_renderer = self.world.get_component(eid, MeshRenderer)
            if mesh_renderer is not None:
                self._layout.addWidget(self._make_mesh_renderer_section(mesh_renderer))

            material = self.world.get_component(eid, Material)
            if material is not None:
                self._layout.addWidget(self._make_material_section(material))

            rigidbody = self.world.get_component(eid, Rigidbody)
            if rigidbody is not None:
                self._layout.addWidget(self._make_rigidbody_section(rigidbody))

            collider = self.world.get_component(eid, Collider)
            if collider is not None:
                self._layout.addWidget(self._make_collider_section(collider))

            script = self.world.get_component(eid, Script)
            if script is not None:
                self._layout.addWidget(self._make_script_section(eid, script))

            camera = self.world.get_component(eid, Camera)
            if camera is not None:
                self._layout.addWidget(self._make_camera_section(camera))

            emitter = self.world.get_component(eid, ParticleEmitter)
            if emitter is not None:
                self._layout.addWidget(self._make_particle_section(emitter))

        finally:
            self._updating = False

    def _clear_layout(self) -> None:
        # Los primeros _perm_count widgets (luz + separador) son permanentes
        while self._layout.count() > self._perm_count:
            item = self._layout.takeAt(self._perm_count)
            w = item.widget()
            if w is not None and w is not self._placeholder:
                w.deleteLater()

    def _sep(self) -> QFrame:
        s = QFrame()
        s.setFrameShape(QFrame.Shape.HLine)
        s.setStyleSheet(
            "QFrame { color: #1a1a26; background: #1a1a26; border: none;"
            "  max-height: 1px; margin: 4px 0; }"
        )
        return s

    def _make_light_section(self) -> QFrame:
        """Panel permanente de configuración de la luz direccional y shadow map."""
        frame, grid = self._section_frame("Luz Direccional")

        # Checkbox: sombras activas
        grid.addWidget(self._lbl("Sombras"), 0, 0)
        chk = QCheckBox()
        chk.setChecked(True)
        chk.setStyleSheet("QCheckBox { color: #8888a8; border: none; font-size: 11px; }")
        grid.addWidget(chk, 0, 1, 1, 3)

        # Spinbox: bias
        grid.addWidget(self._lbl("Bias"), 1, 0)
        bias_sb = QDoubleSpinBox()
        bias_sb.setRange(0.0001, 0.05)
        bias_sb.setSingleStep(0.0002)
        bias_sb.setDecimals(4)
        bias_sb.setValue(0.003)
        bias_sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        bias_sb.setStyleSheet(_SPIN_STYLE)
        bias_sb.setMinimumWidth(48)
        bias_sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid.addWidget(bias_sb, 1, 1, 1, 3)

        # Conexiones (con guarda hasattr porque shadow_map no existe hasta initializeGL)
        def _sm(self=self):
            return getattr(self.viewport, 'shadow_map', None)

        def on_shadow(state):
            sm = _sm()
            if sm:
                sm.enabled = bool(state)
                self.viewport.update()

        def on_bias(val):
            sm = _sm()
            if sm:
                sm.bias = val
                self.viewport.update()

        chk.stateChanged.connect(on_shadow)
        bias_sb.valueChanged.connect(on_bias)
        return frame

    def _make_post_process_section(self) -> QFrame:
        """Parámetros editables de los efectos de post-procesado."""
        frame, grid = self._section_frame("Post-processing")

        def _pp(self=self):
            return getattr(self.viewport, 'post_process', None)

        # Exposure
        grid.addWidget(self._lbl("Exposure"), 0, 0)
        exp_sb = QDoubleSpinBox()
        exp_sb.setRange(0.1, 5.0)
        exp_sb.setSingleStep(0.1)
        exp_sb.setDecimals(2)
        exp_sb.setValue(1.0)
        exp_sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        exp_sb.setStyleSheet(_SPIN_STYLE)
        exp_sb.setMinimumWidth(48)
        exp_sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid.addWidget(exp_sb, 0, 1, 1, 3)

        # Vignette intensity
        grid.addWidget(self._lbl("Viñeta"), 1, 0)
        vig_sb = QDoubleSpinBox()
        vig_sb.setRange(0.0, 4.0)
        vig_sb.setSingleStep(0.1)
        vig_sb.setDecimals(2)
        vig_sb.setValue(1.5)
        vig_sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        vig_sb.setStyleSheet(_SPIN_STYLE)
        vig_sb.setMinimumWidth(48)
        vig_sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid.addWidget(vig_sb, 1, 1, 1, 3)

        def on_exposure(val):
            pp = _pp()
            if pp:
                pp.exposure = val
                self.viewport.update()

        def on_vignette(val):
            pp = _pp()
            if pp:
                pp.vignette_intensity = val
                self.viewport.update()

        exp_sb.valueChanged.connect(on_exposure)
        vig_sb.valueChanged.connect(on_vignette)
        return frame

    def refresh_transform(self) -> None:
        """Actualiza solo los spinboxes del Transform sin reconstruir el panel.
        Llamado durante el drag del gizmo para reflejar cambios en tiempo real."""
        if self._entity_id is None or not self._pos_boxes:
            return
        t = self.world.get_component(self._entity_id, Transform)
        if t is None:
            return
        self._updating = True
        try:
            for sb, v in zip(self._pos_boxes, t.position): sb.setValue(float(v))
            for sb, v in zip(self._rot_boxes, t.rotation): sb.setValue(float(v))
            for sb, v in zip(self._sca_boxes, t.scale):    sb.setValue(float(v))
        finally:
            self._updating = False

    # ------------------------------------------------------------------ #
    def _make_transform_section(self, transform: Transform) -> QFrame:
        frame, grid = self._section_frame("Transform")

        px, py, pz = self._vec3_row(grid, 0, "Position", transform.position, -10000, 10000, 0.1)
        rx, ry, rz = self._vec3_row(grid, 1, "Rotation", transform.rotation,    -360,   360, 1.0)
        sx, sy, sz = self._vec3_row(grid, 2, "Scale",    transform.scale,       0.001, 10000, 0.1)
        self._pos_boxes = [px, py, pz]
        self._rot_boxes = [rx, ry, rz]
        self._sca_boxes = [sx, sy, sz]

        def apply_pos():
            if not self._updating:
                transform.position[:] = [px.value(), py.value(), pz.value()]
                self.viewport.update()

        def apply_rot():
            if not self._updating:
                transform.rotation[:] = [rx.value(), ry.value(), rz.value()]
                self.viewport.update()

        def apply_scale():
            if not self._updating:
                transform.scale[:] = [sx.value(), sy.value(), sz.value()]
                self.viewport.update()

        for sb in (px, py, pz): sb.valueChanged.connect(apply_pos)
        for sb in (rx, ry, rz): sb.valueChanged.connect(apply_rot)
        for sb in (sx, sy, sz): sb.valueChanged.connect(apply_scale)

        return frame

    def _make_mesh_renderer_section(self, mr: MeshRenderer) -> QFrame:
        frame, grid = self._section_frame("Mesh Renderer")

        # Mesh name — lista dinámica desde el registro del viewport -------
        available = (
            list(self.viewport.mesh_registry.keys())
            if hasattr(self.viewport, 'mesh_registry') and self.viewport.mesh_registry
            else _AVAILABLE_MESHES
        )
        if mr.mesh_name not in available:
            available = [mr.mesh_name] + available
        grid.addWidget(self._lbl("Mesh"), 0, 0)
        combo = QComboBox()
        combo.addItems(available)
        combo.setCurrentText(mr.mesh_name)
        combo.setStyleSheet(
            "QComboBox { background: #1e1e1e; color: #dcdcdc;"
            "  border: 1px solid #3a3a3a; padding: 2px; }"
            "QComboBox QAbstractItemView { background: #1e1e1e; color: #dcdcdc;"
            "  selection-background-color: #4a7cb8; }"
        )
        grid.addWidget(combo, 0, 1, 1, 3)

        # Color button ----------------------------------------------------
        grid.addWidget(self._lbl("Color"), 1, 0)
        color_btn = QPushButton()
        color_btn.setFixedHeight(22)
        self._refresh_color_btn(color_btn, mr.color)
        grid.addWidget(color_btn, 1, 1, 1, 3)

        # Visible checkbox ------------------------------------------------
        grid.addWidget(self._lbl("Visible"), 2, 0)
        check = QCheckBox()
        check.setChecked(mr.visible)
        grid.addWidget(check, 2, 1)

        # Connections -----------------------------------------------------
        def on_mesh(text):
            if not self._updating:
                mr.mesh_name = text
                self.viewport.update()

        def on_color():
            r, g, b = mr.color
            qc = QColor(int(r * 255), int(g * 255), int(b * 255))
            picked = QColorDialog.getColor(qc, self, "Seleccionar color")
            if picked.isValid():
                mr.color[:] = [
                    picked.red()   / 255.0,
                    picked.green() / 255.0,
                    picked.blue()  / 255.0,
                ]
                self._refresh_color_btn(color_btn, mr.color)
                self.viewport.update()

        def on_visible(state):
            if not self._updating:
                mr.visible = bool(state)
                self.viewport.update()

        combo.currentTextChanged.connect(on_mesh)
        color_btn.clicked.connect(on_color)
        check.stateChanged.connect(on_visible)

        return frame

    # ------------------------------------------------------------------ #
    def _make_material_section(self, mat: 'Material') -> QFrame:
        """Panel del componente Material PBR."""
        frame, grid = self._section_frame("Material PBR")
        r = 0

        # Albedo color -------------------------------------------------------
        grid.addWidget(self._lbl("Albedo"), r, 0)
        albedo_btn = QPushButton()
        albedo_btn.setFixedHeight(22)
        self._refresh_color_btn(albedo_btn, mat.albedo)
        grid.addWidget(albedo_btn, r, 1, 1, 3); r += 1

        def on_albedo():
            qc = QColor(int(mat.albedo[0]*255), int(mat.albedo[1]*255), int(mat.albedo[2]*255))
            picked = QColorDialog.getColor(qc, self, "Albedo")
            if picked.isValid():
                mat.albedo[:] = [picked.red()/255.0, picked.green()/255.0, picked.blue()/255.0]
                self._refresh_color_btn(albedo_btn, mat.albedo)
                self.viewport.update()
        albedo_btn.clicked.connect(on_albedo)

        # Metallic -----------------------------------------------------------
        grid.addWidget(self._lbl("Metallic"), r, 0)
        met_sb = QDoubleSpinBox()
        met_sb.setRange(0.0, 1.0); met_sb.setSingleStep(0.05); met_sb.setDecimals(3)
        met_sb.setValue(float(mat.metallic))
        met_sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        met_sb.setStyleSheet(_SPIN_STYLE); met_sb.setMinimumWidth(48)
        met_sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid.addWidget(met_sb, r, 1, 1, 3); r += 1
        met_sb.valueChanged.connect(lambda v: setattr(mat, 'metallic', float(v)) or self.viewport.update())

        # Roughness ----------------------------------------------------------
        grid.addWidget(self._lbl("Roughness"), r, 0)
        rough_sb = QDoubleSpinBox()
        rough_sb.setRange(0.0, 1.0); rough_sb.setSingleStep(0.05); rough_sb.setDecimals(3)
        rough_sb.setValue(float(mat.roughness))
        rough_sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        rough_sb.setStyleSheet(_SPIN_STYLE); rough_sb.setMinimumWidth(48)
        rough_sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid.addWidget(rough_sb, r, 1, 1, 3); r += 1
        rough_sb.valueChanged.connect(lambda v: setattr(mat, 'roughness', float(v)) or self.viewport.update())

        # Emission color -----------------------------------------------------
        grid.addWidget(self._lbl("Emision"), r, 0)
        em_btn = QPushButton()
        em_btn.setFixedHeight(22)
        self._refresh_color_btn(em_btn, mat.emission)
        grid.addWidget(em_btn, r, 1, 1, 3); r += 1

        def on_emission():
            qc = QColor(int(mat.emission[0]*255), int(mat.emission[1]*255), int(mat.emission[2]*255))
            picked = QColorDialog.getColor(qc, self, "Emision")
            if picked.isValid():
                mat.emission[:] = [picked.red()/255.0, picked.green()/255.0, picked.blue()/255.0]
                self._refresh_color_btn(em_btn, mat.emission)
                self.viewport.update()
        em_btn.clicked.connect(on_emission)

        # Emission strength --------------------------------------------------
        grid.addWidget(self._lbl("Em.Fuerza"), r, 0)
        ems_sb = QDoubleSpinBox()
        ems_sb.setRange(0.0, 50.0); ems_sb.setSingleStep(0.1); ems_sb.setDecimals(2)
        ems_sb.setValue(float(mat.emission_strength))
        ems_sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        ems_sb.setStyleSheet(_SPIN_STYLE); ems_sb.setMinimumWidth(48)
        ems_sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid.addWidget(ems_sb, r, 1, 1, 3); r += 1
        ems_sb.valueChanged.connect(lambda v: setattr(mat, 'emission_strength', float(v)) or self.viewport.update())

        # Texture path fields ------------------------------------------------
        def _tex_row(row, label, attr):
            grid.addWidget(self._lbl(label), row, 0)
            le = QLineEdit(getattr(mat, attr))
            le.setPlaceholderText("Ruta a textura...")
            le.setStyleSheet(
                "QLineEdit { background:#1e1e1e; color:#dcdcdc;"
                "  border:1px solid #3a3a3a; padding:2px 4px; font-size:10px; }"
            )
            browse = QPushButton("..."); browse.setFixedWidth(24)
            browse.setStyleSheet(
                "QPushButton { background:#2a2a2a; color:#ccc;"
                "  border:1px solid #3a3a3a; border-radius:3px; padding:1px; }"
                "QPushButton:hover { background:#383838; }"
            )
            hbox = QHBoxLayout(); hbox.setContentsMargins(0, 0, 0, 0); hbox.setSpacing(2)
            hbox.addWidget(le); hbox.addWidget(browse)
            container = QWidget(); container.setLayout(hbox)
            grid.addWidget(container, row, 1, 1, 3)

            def _on_text(text, a=attr):
                setattr(mat, a, text)

            def _browse(a=attr, edit=le):
                p, _ = QFileDialog.getOpenFileName(
                    self, "Seleccionar textura", "", "Imagenes (*.png *.jpg *.jpeg *.tga *.bmp)"
                )
                if p:
                    edit.setText(p)
                    setattr(mat, a, p)
                    self.viewport.update()

            le.textChanged.connect(_on_text)
            browse.clicked.connect(_browse)

        _tex_row(r, "Albedo Map",  "albedo_map");              r += 1
        _tex_row(r, "Normal Map",  "normal_map");              r += 1
        _tex_row(r, "MetalRough",  "metallic_roughness_map");  r += 1
        _tex_row(r, "AO Map",      "ao_map");                  r += 1

        return frame

    # ------------------------------------------------------------------ #
    def _make_rigidbody_section(self, rb: Rigidbody) -> QFrame:
        frame, grid = self._section_frame("Rigidbody")

        def _sb(row, label, val, lo, hi, step, decimals, setter):
            grid.addWidget(self._lbl(label), row, 0)
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi); sb.setSingleStep(step); sb.setDecimals(decimals)
            sb.setValue(float(val))
            sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            sb.setStyleSheet(_SPIN_STYLE); sb.setMinimumWidth(48)
            sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            grid.addWidget(sb, row, 1, 1, 3)
            if not self._updating:
                sb.valueChanged.connect(lambda v: setter(v))
            return sb

        def _chk(row, label, val, setter):
            grid.addWidget(self._lbl(label), row, 0)
            chk = QCheckBox(); chk.setChecked(val)
            chk.setStyleSheet("QCheckBox { color: #8888a8; border: none; font-size: 11px; }")
            grid.addWidget(chk, row, 1, 1, 3)
            chk.stateChanged.connect(lambda s: setter(bool(s)))
            return chk

        _sb(0, "Masa",        rb.mass,        0.01, 1000.0, 0.1, 2, lambda v: setattr(rb, 'mass', v))
        _sb(1, "Restitución", rb.restitution, 0.0,  1.0,   0.05, 2, lambda v: setattr(rb, 'restitution', v))
        _sb(2, "Fricción",    rb.friction,    0.0,  1.0,   0.05, 2, lambda v: setattr(rb, 'friction', v))
        _chk(3, "Gravedad",  rb.use_gravity, lambda v: setattr(rb, 'use_gravity', v))
        _chk(4, "Estático",  rb.is_static,   lambda v: setattr(rb, 'is_static',  v))
        return frame

    def _make_collider_section(self, col: Collider) -> QFrame:
        frame, grid = self._section_frame("Collider")

        # Shape combo
        grid.addWidget(self._lbl("Forma"), 0, 0)
        combo = QComboBox()
        combo.addItems(["aabb", "sphere"])
        combo.setCurrentText(col.shape)
        combo.setStyleSheet(
            "QComboBox { background: #0c0c14; color: #c0c0d8; border: 1px solid #2a2a3c; border-radius: 4px; padding: 2px 6px; font-size: 11px; }"
            "QComboBox QAbstractItemView { background: #0c0c14; color: #c0c0d8; border: 1px solid #2a2a3c; selection-background-color: #6c63ff33; }"
        )
        grid.addWidget(combo, 0, 1, 1, 3)
        combo.currentTextChanged.connect(lambda t: setattr(col, 'shape', t))

        # Size (AABB)
        sx, sy, sz = self._vec3_row(grid, 1, "Tamaño", col.size, 0.01, 100.0, 0.1)
        for sb, axis in zip([sx, sy, sz], range(3)):
            sb.valueChanged.connect(lambda v, a=axis: col.size.__setitem__(a, v))

        # Radius (Sphere)
        grid.addWidget(self._lbl("Radio"), 2, 0)
        r_sb = QDoubleSpinBox(); r_sb.setRange(0.01, 100.0); r_sb.setSingleStep(0.05)
        r_sb.setDecimals(3); r_sb.setValue(float(col.radius))
        r_sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        r_sb.setStyleSheet(_SPIN_STYLE); r_sb.setMinimumWidth(48)
        r_sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid.addWidget(r_sb, 2, 1, 1, 3)
        r_sb.valueChanged.connect(lambda v: setattr(col, 'radius', v))

        # Offset
        ox, oy, oz = self._vec3_row(grid, 3, "Offset", col.offset, -100.0, 100.0, 0.1)
        for sb, axis in zip([ox, oy, oz], range(3)):
            sb.valueChanged.connect(lambda v, a=axis: col.offset.__setitem__(a, v))

        return frame

    # ------------------------------------------------------------------ #
    def _make_camera_section(self, cam: Camera) -> QFrame:
        frame, grid = self._section_frame("Camera")

        def _sb(row, label, val, lo, hi, step, dec, setter):
            grid.addWidget(self._lbl(label), row, 0)
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi); sb.setSingleStep(step); sb.setDecimals(dec)
            sb.setValue(float(val))
            sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            sb.setStyleSheet(_SPIN_STYLE); sb.setMinimumWidth(48)
            sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            grid.addWidget(sb, row, 1, 1, 3)
            sb.valueChanged.connect(lambda v: setter(v))
            return sb

        # Proyección
        grid.addWidget(self._lbl("Proyección"), 0, 0)
        proj_combo = QComboBox()
        proj_combo.addItems(["perspective", "orthographic"])
        proj_combo.setCurrentText(cam.projection)
        proj_combo.setStyleSheet(
            "QComboBox { background: #0c0c14; color: #c0c0d8; border: 1px solid #2a2a3c; border-radius: 4px; padding: 2px 6px; font-size: 11px; }"
            "QComboBox QAbstractItemView { background: #0c0c14; color: #c0c0d8; border: 1px solid #2a2a3c; selection-background-color: #6c63ff33; }"
        )
        grid.addWidget(proj_combo, 0, 1, 1, 3)
        proj_combo.currentTextChanged.connect(lambda t: setattr(cam, 'projection', t))

        _sb(1, "FOV",        cam.fov,        5.0,  170.0, 1.0, 1, lambda v: setattr(cam, 'fov', v))
        _sb(2, "Near",       cam.near,       0.001, 100.0, 0.01, 3, lambda v: setattr(cam, 'near', v))
        _sb(3, "Far",        cam.far,        1.0, 10000.0, 10.0, 1, lambda v: setattr(cam, 'far', v))
        _sb(4, "Ortho Size", cam.ortho_size, 0.5,  500.0,  0.5, 1, lambda v: setattr(cam, 'ortho_size', v))

        # is_main checkbox
        grid.addWidget(self._lbl("Principal"), 5, 0)
        chk = QCheckBox(); chk.setChecked(cam.is_main)
        chk.setStyleSheet("QCheckBox { color: #8888a8; border: none; font-size: 11px; }")
        grid.addWidget(chk, 5, 1, 1, 3)
        chk.stateChanged.connect(lambda s: setattr(cam, 'is_main', bool(s)))

        return frame

    # ------------------------------------------------------------------ #
    def _make_entity_header(self, eid: int) -> QLabel:
        """Muestra el nombre de la entidad como encabezado del inspector."""
        name = self.world.get_entity_name(eid)
        lbl = QLabel(name)
        lbl.setStyleSheet(
            "QLabel { font-size: 13px; font-weight: 600; color: #d0d0e8; letter-spacing: 0.01em;"
            "  padding: 6px 4px 4px 4px; border: none;"
            "  border-bottom: 1px solid #1e1e2c; }"
        )
        return lbl

    # ------------------------------------------------------------------ #
    def _make_particle_section(self, em: ParticleEmitter) -> QFrame:
        frame, grid = self._section_frame("Particle Emitter")

        def _sb(row, col, label, val, lo, hi, step, dec, setter, span=1):
            if label:
                grid.addWidget(self._lbl(label), row, col)
                col += 1
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi); sb.setSingleStep(step); sb.setDecimals(dec)
            sb.setValue(float(val))
            sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            sb.setStyleSheet(_SPIN_STYLE); sb.setMinimumWidth(44)
            sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            grid.addWidget(sb, row, col, 1, span)
            sb.valueChanged.connect(setter)
            return sb

        def _isb(row, col, label, val, lo, hi, setter):
            if label:
                grid.addWidget(self._lbl(label), row, col)
                col += 1
            from PyQt6.QtWidgets import QSpinBox
            sb = QSpinBox(); sb.setRange(lo, hi); sb.setValue(int(val))
            sb.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            sb.setStyleSheet(_SPIN_STYLE.replace("QDoubleSpinBox", "QSpinBox"))
            sb.setMinimumWidth(44)
            sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            grid.addWidget(sb, row, col, 1, 3)
            sb.valueChanged.connect(setter)
            return sb

        r = 0
        _isb(r, 0, "Máx part.", em.max_particles, 1, 5000,
             lambda v: setattr(em, 'max_particles', v)); r += 1
        _sb(r, 0, "Emisión/s", em.emission_rate, 0, 500, 1, 1,
            lambda v: setattr(em, 'emission_rate', v), span=3); r += 1

        # Vida min / max en la misma fila
        grid.addWidget(self._lbl("Vida"), r, 0)
        _sb(r, 1, "", em.lifetime_min, 0.01, 60, 0.1, 2,
            lambda v: setattr(em, 'lifetime_min', v))
        _sb(r, 2, "", em.lifetime_max, 0.01, 60, 0.1, 2,
            lambda v: setattr(em, 'lifetime_max', v)); r += 1

        grid.addWidget(self._lbl("Vel"), r, 0)
        _sb(r, 1, "", em.speed_min, 0, 50, 0.1, 2,
            lambda v: setattr(em, 'speed_min', v))
        _sb(r, 2, "", em.speed_max, 0, 50, 0.1, 2,
            lambda v: setattr(em, 'speed_max', v)); r += 1

        grid.addWidget(self._lbl("Tam"), r, 0)
        _sb(r, 1, "", em.size_start, 0, 20, 0.05, 3,
            lambda v: setattr(em, 'size_start', v))
        _sb(r, 2, "", em.size_end, 0, 20, 0.05, 3,
            lambda v: setattr(em, 'size_end', v)); r += 1

        # Colores RGBA (2 filas, 4 spinboxes cada una)
        for label, attr in [("C.Ini", 'color_start'), ("C.Fin", 'color_end')]:
            grid.addWidget(self._lbl(label), r, 0)
            col_arr = getattr(em, attr)
            for ci, ch in enumerate(['R', 'G', 'B', 'A']):
                # Hack: usar solo 3 spinboxes en cols 1-3, A aparece col 3
                if ci >= 3: break
                sb = QDoubleSpinBox(); sb.setRange(0, 1); sb.setSingleStep(0.05)
                sb.setDecimals(2); sb.setValue(float(col_arr[ci]))
                sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
                sb.setStyleSheet(_SPIN_STYLE); sb.setMinimumWidth(40)
                grid.addWidget(sb, r, ci + 1)
                _a = attr; _i = ci
                sb.valueChanged.connect(
                    lambda v, a=_a, i=_i: getattr(em, a).__setitem__(i, v))
            # Alpha en siguiente fila
            r += 1
            grid.addWidget(self._lbl("  Alpha"), r, 0)
            sba = QDoubleSpinBox(); sba.setRange(0, 1); sba.setSingleStep(0.05)
            sba.setDecimals(2); sba.setValue(float(col_arr[3]))
            sba.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            sba.setStyleSheet(_SPIN_STYLE); sba.setMinimumWidth(48)
            sba.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            grid.addWidget(sba, r, 1, 1, 3)
            _a = attr
            sba.valueChanged.connect(lambda v, a=_a: getattr(em, a).__setitem__(3, v))
            r += 1

        _sb(r, 0, "Gravedad", em.gravity_scale, -5, 5, 0.1, 2,
            lambda v: setattr(em, 'gravity_scale', v), span=3); r += 1

        # Forma del emisor
        grid.addWidget(self._lbl("Forma"), r, 0)
        shape_combo = QComboBox()
        shape_combo.addItems(["point", "sphere", "cone"])
        shape_combo.setCurrentText(em.shape)
        shape_combo.setStyleSheet(
            "QComboBox { background:#0c0c14; color:#c0c0d8; border:1px solid #2a2a3c; border-radius:4px; padding:2px 6px; font-size:11px; }"
            "QComboBox QAbstractItemView { background:#1e1e1e; color:#dcdcdc; selection-background-color:#4a7cb8; }")
        grid.addWidget(shape_combo, r, 1, 1, 3)
        shape_combo.currentTextChanged.connect(lambda t: setattr(em, 'shape', t)); r += 1

        grid.addWidget(self._lbl("Radio"), r, 0)
        _sb(r, 1, "", em.shape_radius, 0, 20, 0.05, 3,
            lambda v: setattr(em, 'shape_radius', v), span=3); r += 1
        grid.addWidget(self._lbl("Ángulo°"), r, 0)
        _sb(r, 1, "", em.cone_angle, 0, 90, 1, 1,
            lambda v: setattr(em, 'cone_angle', v), span=3); r += 1

        # Burst
        grid.addWidget(self._lbl("Burst"), r, 0)
        burst_chk = QCheckBox(); burst_chk.setChecked(em.burst)
        burst_chk.setStyleSheet("QCheckBox{color:#dcdcdc;border:none;}")
        grid.addWidget(burst_chk, r, 1)
        burst_chk.stateChanged.connect(lambda s: setattr(em, 'burst', bool(s))); r += 1
        _isb(r, 0, "Cant.", em.burst_count, 0, 5000,
             lambda v: setattr(em, 'burst_count', v)); r += 1

        # ── Presets ────────────────────────────────────────────────────
        import os as _os
        _presets_dir = _os.path.normpath(
            _os.path.join(_os.path.dirname(__file__), '..', 'assets', 'particles'))

        from engine.rendering import list_presets, apply_preset
        presets = list_presets(_presets_dir)

        if presets:
            grid.addWidget(self._lbl("Preset"), r, 0)
            preset_combo = QComboBox()
            preset_combo.addItems([name for name, _ in presets])
            preset_combo.setStyleSheet(shape_combo.styleSheet())
            grid.addWidget(preset_combo, r, 1, 1, 2)

            load_btn = QPushButton("Cargar")
            load_btn.setStyleSheet(
                "QPushButton{background:#2a4a70;color:#ccc;border:1px solid #3a5a90;"
                "border-radius:3px;padding:2px 6px;}"
                "QPushButton:hover{background:#6c63ff44;color:#c4bcff;}")
            grid.addWidget(load_btn, r, 3)

            def _load_preset():
                idx = preset_combo.currentIndex()
                if 0 <= idx < len(presets):
                    apply_preset(presets[idx][1], em)
                    self.viewport.update()
                    QTimer.singleShot(0, self._rebuild)

            load_btn.clicked.connect(_load_preset)

        return frame

    # ------------------------------------------------------------------ #
    def _make_script_section(self, eid: int, script: Script) -> QFrame:
        """Panel del componente Script: ruta, estado, botones abrir/recargar."""
        frame = QFrame()
        frame.setStyleSheet(_FRAME_STYLE)
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(8, 6, 8, 8)
        vbox.setSpacing(4)

        header = QLabel("Script")
        header.setStyleSheet(_HEADER_STYLE)
        vbox.addWidget(header)

        # ── Fila ruta + examinar ──────────────────────────────────────
        path_row = QHBoxLayout()
        path_edit = QLineEdit(script.path)
        path_edit.setPlaceholderText("Ruta al archivo .py …")
        path_edit.setStyleSheet(
            "QLineEdit { background: #1e1e1e; color: #dcdcdc;"
            "  border: 1px solid #3a3a3a; padding: 2px 4px; }"
        )
        path_row.addWidget(path_edit)

        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(28)
        browse_btn.setStyleSheet(
            "QPushButton { background: #2a2a2a; color: #ccc;"
            "  border: 1px solid #3a3a3a; border-radius: 3px; padding: 2px; }"
            "QPushButton:hover { background: #6c63ff22; border-color: #6c63ff66; color: #c4bcff; }"
        )
        path_row.addWidget(browse_btn)
        vbox.addLayout(path_row)

        # ── Estado ───────────────────────────────────────────────────
        status_lbl = QLabel()
        status_lbl.setWordWrap(True)
        status_lbl.setStyleSheet("font-size: 10px; border: none; padding: 1px 0;")
        vbox.addWidget(status_lbl)

        # ── Botones abrir / recargar ──────────────────────────────────
        btn_row = QHBoxLayout()

        open_btn = QPushButton("Abrir en editor")
        open_btn.setStyleSheet(
            "QPushButton { background: #2a2a2a; color: #ccc;"
            "  border: 1px solid #3a3a3a; border-radius: 3px; padding: 3px 8px; }"
            "QPushButton:hover { background: #6c63ff22; border-color: #6c63ff66; color: #c4bcff; }"
        )
        btn_row.addWidget(open_btn)

        reload_btn = QPushButton("Recargar")
        reload_btn.setStyleSheet(open_btn.styleSheet())
        btn_row.addWidget(reload_btn)
        vbox.addLayout(btn_row)

        # ── Helpers ───────────────────────────────────────────────────
        def _ss():
            return getattr(self.viewport, 'script_system', None)

        def _refresh_status():
            ss = _ss()
            if ss is None:
                status_lbl.setText("")
                return
            st = ss.status(eid)
            if st == "ok":
                status_lbl.setStyleSheet("color: #5fbf5f; font-size: 10px; border: none;")
                cls = type(ss._instances[eid]).__name__
                status_lbl.setText(f"✓  {cls}")
            elif st == "error":
                status_lbl.setStyleSheet("color: #e05a5a; font-size: 10px; border: none;")
                msg = ss.error_message(eid)
                # Mostrar solo primera línea del traceback
                first = msg.strip().splitlines()[-1] if msg.strip() else "Error"
                status_lbl.setText(f"✗  {first}")
            else:
                status_lbl.setStyleSheet("color: #888; font-size: 10px; border: none;")
                status_lbl.setText("Sin cargar")

        def _do_reload():
            script.path = path_edit.text()
            ss = _ss()
            if ss:
                ss.load_one(eid)
            _refresh_status()

        def _on_path_changed(text):
            script.path = text

        def _browse():
            scripts_dir = "assets/scripts"
            p, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar script", scripts_dir, "Scripts Python (*.py)"
            )
            if p:
                path_edit.setText(p)
                script.path = p
                _do_reload()

        def _open_in_editor():
            p = script.path
            if not p:
                return
            import subprocess, sys as _sys
            try:
                if _sys.platform == 'win32':
                    import os as _os
                    _os.startfile(p)
                elif _sys.platform == 'darwin':
                    subprocess.run(['open', p])
                else:
                    subprocess.run(['xdg-open', p])
            except Exception as exc:
                status_lbl.setText(f"No se pudo abrir: {exc}")

        path_edit.textChanged.connect(_on_path_changed)
        browse_btn.clicked.connect(_browse)
        open_btn.clicked.connect(_open_in_editor)
        reload_btn.clicked.connect(_do_reload)

        # Mostrar estado actual al construir la sección
        _refresh_status()
        return frame

    # ------------------------------------------------------------------ #
    def _section_frame(self, title: str) -> tuple:
        frame = QFrame()
        frame.setStyleSheet(_FRAME_STYLE)
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(10, 8, 10, 10)
        vbox.setSpacing(6)

        header = QLabel(title)
        header.setStyleSheet(_HEADER_STYLE)
        vbox.addWidget(header)

        grid = QGridLayout()
        grid.setColumnMinimumWidth(0, 56)
        grid.setColumnMinimumWidth(1, 44)
        grid.setColumnMinimumWidth(2, 44)
        grid.setColumnMinimumWidth(3, 44)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(5)
        vbox.addLayout(grid)

        return frame, grid

    def _vec3_row(self, grid, row: int, label: str, values, vmin, vmax, step):
        grid.addWidget(self._lbl(label), row, 0)
        boxes = []
        for col, val in enumerate(values, start=1):
            sb = QDoubleSpinBox()
            sb.setRange(vmin, vmax)
            sb.setSingleStep(step)
            sb.setDecimals(3)
            sb.setValue(float(val))
            sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            sb.setStyleSheet(_SPIN_STYLE)
            # Ancho mínimo explícito para que no se salga del contenedor
            # cuando el dock del inspector se estrecha.
            sb.setMinimumWidth(48)
            sb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            grid.addWidget(sb, row, col)
            boxes.append(sb)
        return boxes[0], boxes[1], boxes[2]

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(_LABEL_STYLE)
        return lbl

    def _refresh_color_btn(self, btn: QPushButton, color: np.ndarray) -> None:
        r, g, b = int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
        lum = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
        fg = "#000" if lum > 0.5 else "#eee"
        btn.setStyleSheet(
            f"QPushButton {{ background: rgb({r},{g},{b}); color: {fg};"
            "  border: 1px solid #2a2a3c; border-radius: 4px;"
            "  font-size: 10px; letter-spacing: 0.04em; }}"
        )
        btn.setText(f"#{r:02X}{g:02X}{b:02X}  ({color[0]:.2f}, {color[1]:.2f}, {color[2]:.2f})")
