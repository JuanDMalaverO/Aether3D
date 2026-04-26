"""
RenderSystem - Itera sobre entidades con Transform + MeshRenderer y las dibuja.
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
        self.shader       = shader
        self.mesh_registry = mesh_registry
        self.view:        np.ndarray | None = None
        self.projection:  np.ndarray | None = None
        self.camera_pos:  np.ndarray | None = None
        self.light_dir:   np.ndarray = np.array([-0.5, -1.0, -0.3], dtype=np.float32)
        self.shadow_map   = None   # ShadowMap | None, inyectado por el viewport

    def update(self, dt: float) -> None:
        if self.view is None or self.projection is None:
            return

        self.shader.use()
        self.shader.set_mat4("uView",       self.view)
        self.shader.set_mat4("uProjection", self.projection)
        self.shader.set_vec3("uLightDir",   self.light_dir)
        if self.camera_pos is not None:
            self.shader.set_vec3("uViewPos", self.camera_pos)

        # Uniforms del shadow map
        sm = self.shadow_map
        if sm and sm.enabled:
            sm.bind_shadow_texture(1)
            self.shader.set_int  ("uShadowMap",         1)
            self.shader.set_mat4 ("uLightSpaceMatrix",  sm.light_space_matrix)
            self.shader.set_float("uShadowBias",        sm.bias)
            self.shader.set_int  ("uShadowEnabled",     1)
        else:
            self.shader.set_int("uShadowEnabled", 0)
            # Evitar que el sampler quede sin textura válida
            self.shader.set_mat4("uLightSpaceMatrix", np.eye(4, dtype=np.float32))

        for entity_id, (transform, mesh_renderer) in self.world.query(Transform, MeshRenderer):
            if not mesh_renderer.visible:
                continue
            mesh = self.mesh_registry.get(mesh_renderer.mesh_name)
            if mesh is None:
                continue
            model = transform.world_matrix(self.world)
            self.shader.set_mat4("uModel", model)
            self.shader.set_vec3("uColor", mesh_renderer.color)
            mesh.draw()
