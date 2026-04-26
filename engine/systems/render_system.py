"""
RenderSystem — Itera sobre entidades con Transform + MeshRenderer y las dibuja.
Soporta dos render paths:
  - PBR (pbr_shader):   entidades que tienen componente Material
  - Blinn-Phong básico (self.shader): entidades sin Material (compatibilidad)
"""
from OpenGL.GL import *
import numpy as np
from engine.ecs.system import System
from engine.ecs.world import World
from engine.components.transform import Transform
from engine.components.mesh import MeshRenderer
from engine.rendering.shader import Shader
from engine.rendering.mesh import Mesh


class RenderSystem(System):
    def __init__(self, world: World, shader: Shader, mesh_registry: dict[str, Mesh]):
        super().__init__(world)
        self.shader        = shader
        self.mesh_registry = mesh_registry
        self.view:         np.ndarray | None = None
        self.projection:   np.ndarray | None = None
        self.camera_pos:   np.ndarray | None = None
        self.light_dir:    np.ndarray = np.array([-0.5, -1.0, -0.3], dtype=np.float32)
        self.shadow_map    = None   # ShadowMap | None, inyectado por el viewport

        # PBR — inyectados por el viewport en initializeGL
        self.pbr_shader:        Shader | None = None
        self.material_registry  = None   # MaterialRegistry | None
        self.ibl                = None   # IBL | None
        self._skybox_tex:       int    = 0   # texture ID del cubemap activo

    def update(self, dt: float) -> None:
        if self.view is None or self.projection is None:
            return

        # ── Configurar shader básico (siempre disponible) ─────────────────
        sm = self.shadow_map
        self._setup_basic_shader(sm)

        # ── Configurar shader PBR (si disponible) ─────────────────────────
        if self.pbr_shader is not None:
            self._setup_pbr_shader(sm)

        # ── Dibujar entidades ─────────────────────────────────────────────
        from engine.components.material import Material

        for entity_id, (transform, mesh_renderer) in self.world.query(Transform, MeshRenderer):
            if not mesh_renderer.visible:
                continue
            mesh = self.mesh_registry.get(mesh_renderer.mesh_name)
            if mesh is None:
                continue

            model = transform.world_matrix(self.world)
            mat   = self.world.get_component(entity_id, Material)

            if mat is not None and self.pbr_shader is not None:
                # ── Ruta PBR ──────────────────────────────────────────────
                self.pbr_shader.use()
                self.pbr_shader.set_mat4("uModel", model)
                self._bind_material(mat)
            else:
                # ── Ruta básica Blinn-Phong ───────────────────────────────
                self.shader.use()
                self.shader.set_mat4("uModel", model)
                self.shader.set_vec3("uColor", mesh_renderer.color)

            mesh.draw()

    # ── Helpers de configuración de shaders ──────────────────────────────
    def _setup_basic_shader(self, sm) -> None:
        """Configura las matrices y uniforms globales del shader básico."""
        s = self.shader
        s.use()
        s.set_mat4("uView",       self.view)
        s.set_mat4("uProjection", self.projection)
        s.set_vec3("uLightDir",   self.light_dir)
        if self.camera_pos is not None:
            s.set_vec3("uViewPos", self.camera_pos)

        if sm and sm.enabled:
            sm.bind_shadow_texture(1)
            s.set_int  ("uShadowMap",        1)
            s.set_mat4 ("uLightSpaceMatrix", sm.light_space_matrix)
            s.set_float("uShadowBias",       sm.bias)
            s.set_int  ("uShadowEnabled",    1)
        else:
            s.set_int  ("uShadowEnabled",    0)
            s.set_mat4 ("uLightSpaceMatrix", np.eye(4, dtype=np.float32))

    def _setup_pbr_shader(self, sm) -> None:
        """Configura las matrices y uniforms globales del shader PBR."""
        s = self.pbr_shader
        s.use()
        s.set_mat4("uView",       self.view)
        s.set_mat4("uProjection", self.projection)
        s.set_vec3("uLightDir",   self.light_dir)
        if self.camera_pos is not None:
            s.set_vec3("uViewPos", self.camera_pos)

        if sm and sm.enabled:
            sm.bind_shadow_texture(1)
            s.set_int  ("uShadowMap",        1)
            s.set_mat4 ("uLightSpaceMatrix", sm.light_space_matrix)
            s.set_float("uShadowBias",       sm.bias)
            s.set_int  ("uShadowEnabled",    1)
        else:
            s.set_int  ("uShadowEnabled",    0)
            s.set_mat4 ("uLightSpaceMatrix", np.eye(4, dtype=np.float32))

    def _bind_material(self, mat) -> None:
        """Enlaza los uniforms y texturas del material PBR."""
        s = self.pbr_shader

        s.set_vec3 ("uAlbedo",          mat.albedo)
        s.set_float("uMetallic",        mat.metallic)
        s.set_float("uRoughness",       mat.roughness)
        s.set_vec3 ("uEmission",        mat.emission)
        s.set_float("uEmissionStrength",mat.emission_strength)

        reg = self.material_registry

        # Albedo map (unit 2)
        albedo_tex = reg.get_texture(mat.albedo_map) if reg else 0
        if albedo_tex:
            glActiveTexture(GL_TEXTURE2)
            glBindTexture(GL_TEXTURE_2D, albedo_tex)
            s.set_int("uAlbedoMap",    2)
            s.set_int("uHasAlbedoMap", 1)
        else:
            s.set_int("uHasAlbedoMap", 0)

        # Normal map (unit 3)
        normal_tex = reg.get_texture(mat.normal_map) if reg else 0
        if normal_tex:
            glActiveTexture(GL_TEXTURE3)
            glBindTexture(GL_TEXTURE_2D, normal_tex)
            s.set_int("uNormalMap",    3)
            s.set_int("uHasNormalMap", 1)
        else:
            s.set_int("uHasNormalMap", 0)

        # Metallic-roughness map (unit 4)
        mr_tex = reg.get_texture(mat.metallic_roughness_map) if reg else 0
        if mr_tex:
            glActiveTexture(GL_TEXTURE4)
            glBindTexture(GL_TEXTURE_2D, mr_tex)
            s.set_int("uMetallicRoughnessMap",    4)
            s.set_int("uHasMetallicRoughnessMap", 1)
        else:
            s.set_int("uHasMetallicRoughnessMap", 0)

        # AO map (unit 7)
        ao_tex = reg.get_texture(mat.ao_map) if reg else 0
        if ao_tex:
            glActiveTexture(GL_TEXTURE7)
            glBindTexture(GL_TEXTURE_2D, ao_tex)
            s.set_int("uAoMap",    7)
            s.set_int("uHasAoMap", 1)
        else:
            s.set_int("uHasAoMap", 0)

        # IBL textures (units 5 y 6)
        if self.ibl and self.ibl.enabled:
            glActiveTexture(GL_TEXTURE5)
            glBindTexture(GL_TEXTURE_CUBE_MAP, self.ibl.irradiance_tex)
            s.set_int("uIrradianceMap", 5)
            glActiveTexture(GL_TEXTURE6)
            glBindTexture(GL_TEXTURE_CUBE_MAP, self._skybox_tex)
            s.set_int("uPrefilterMap", 6)
            s.set_int("uIBLEnabled",   1)
        else:
            s.set_int("uIBLEnabled", 0)
