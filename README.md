# Aether3D

> Motor de juego 3D con editor integrado — construido desde cero en Python.

Aether3D es un motor de juego y editor de escenas 3D completo, desarrollado sobre **OpenGL 3.3 Core Profile**, **PyQt6** y una arquitectura **ECS** (Entity Component System) propia. Incluye un pipeline de renderizado PBR físicamente correcto, sistema de física con detección de colisiones, scripting en Python por entidad, sistema de partículas GPU, modo de juego con cámara en primera o tercera persona, y un editor visual con inspector, jerarquía de escena, gizmos y herramientas de escena completas.

---

## Características

### Renderizado
- **Pipeline PBR** — Cook-Torrance GGX con distribución GGX, geometría Smith-Schlick y Fresnel Schlick
- **IBL (Image Based Lighting)** — Irradiance cubemap para difuso + prefiltered environment map para especular con aproximación analítica BRDF (Lagarde)
- **Shadow mapping** — Depth pass con PCF 3×3 y bias adaptativo
- **Post-processing** — ACES filmic tonemapping, viñeta configurable y FXAA, renderizado en FBO HDR GL_RGBA16F
- **Skybox** — Cubemap con 6 caras y soporte para múltiples entornos (espacio, cielo exterior)
- **Sistema de partículas GPU** — GPU instancing con `glDrawArraysInstanced`, billboards con cámara, presets en JSON (fuego, humo, explosión)
- **Grid infinito** — Ray-plane intersection en fragment shader, sin geometría

### Sistema de materiales
- Componente **Material** con albedo, metallic, roughness, emission y soporte de texturas (albedo map, normal map, metallic-roughness map, AO map)
- **MaterialRegistry** — carga y caché de materiales JSON y texturas GL con mipmaps
- 5 materiales de ejemplo: metal pulido, madera, piedra, plástico, emisivo
- Retrocompatibilidad: entidades sin Material usan el shader Blinn-Phong original

### Física
- Sistema de física con integración semi-implícita de Euler
- Detección de colisiones AABB–AABB, Sphere–Sphere y AABB–Sphere
- Resolución de impulsos + Linear Projection para evitar penetración
- Visualización de wireframes de colliders en el editor

### Scripting
- Scripts en Python por entidad con ciclo de vida `on_start`, `on_update`, `on_collision`
- Carga dinámica con `importlib` (recarga en caliente sin reiniciar)
- Módulo `engine.input` — singleton `Input.get_key()` / `Input.get_mouse_delta()` accesible desde cualquier script
- Scripts de ejemplo: `first_person_controller`, `third_person_controller`, `jumper`, `rotate`, `color_changer`

### Sistema de cámaras
- Componente **Camera** con FOV, near/far, proyección perspectiva u ortográfica, `is_main`
- Dropdown en toolbar para previsualizar desde cualquier cámara de la escena sin entrar en Play
- Preview en miniatura (240×135 px) de la cámara principal en la esquina del viewport
- Frustum corto + ícono de cuerpo para cada entidad Camera visible en el editor

### Modo Juego (Play / Pause / Stop)
- Snapshot de escena al entrar en Play; restauración exacta al hacer Stop
- Modo **cámara por script** — si existe un `Camera(is_main=True)`, Play renderiza desde su Transform (controlado por `FirstPersonController` o `ThirdPersonController`)
- Modo **FPS legacy** — si no hay Camera, control WASD + mouse directo sobre el jugador
- Captura de mouse con cursor oculto; Escape como única salida

### Editor
- **Viewport** OpenGL embebido en QOpenGLWidget con cámara orbital estilo Blender
- **Jerarquía** — árbol con drag & drop, padre/hijo, renombrar y eliminar entidades
- **Inspector** dinámico — edición en vivo de todos los componentes: Transform, MeshRenderer, Material, Rigidbody, Collider, Camera, Script, ParticleEmitter
- **Gizmos** de transformación — mover, rotar y escalar con arrastrado por eje
- **Ray picking** — clic para seleccionar entidades por AABB en espacio objeto
- **Contorno** de selección por inflate-normals con `GL_CULL_FACE_FRONT` (sin stencil buffer)
- **Guardar / cargar** escenas en JSON
- **Importar modelos** `.obj` con carga de normales suavizadas y UVs
- Toolbar con velocidad de movimiento WASD configurable (0.25× – 10×)

---

## Instalación

```bash
# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Linux / macOS

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar el editor
python main.py
```

**Requisitos:** Python 3.11+, GPU con soporte OpenGL 3.3 Core Profile.

---

## Controles del editor

| Acción | Control |
|--------|---------|
| Orbitar cámara | MMB + arrastrar |
| Pan | Shift + MMB + arrastrar |
| Zoom | Rueda del ratón |
| Mover en escena | WASD / Shift (subir) / Ctrl (bajar) |
| Seleccionar entidad | Clic izquierdo |
| Menú contextual | Clic derecho sobre entidad |
| Gizmo mover/rotar/escalar | Toolbar → Move / Rotate / Scale |

### Modo Juego

| Acción | Control |
|--------|---------|
| Mover | WASD |
| Saltar | Espacio |
| Girar cámara | Mouse |
| Salir del modo juego | Escape |

---

## Arquitectura

### ECS (Entity Component System)

Las entidades son IDs enteros. Los componentes son dataclasses con datos puros. Los sistemas contienen la lógica.

```python
world = World()
eid = world.create_entity("Jugador")
world.add_component(eid, Transform(position=np.array([0.0, 1.0, 0.0])))
world.add_component(eid, MeshRenderer(mesh_name="capsule"))
world.add_component(eid, Material(albedo=np.array([0.6, 0.8, 1.0]), metallic=0.0, roughness=0.4))
world.add_component(eid, Rigidbody(mass=75.0, use_gravity=True))

# Query multi-componente (iterable eficiente)
for eid, (transform, mesh) in world.query(Transform, MeshRenderer):
    ...
```

### Scripting por entidad

```python
# assets/scripts/mi_script.py
from engine.scripting import BaseScript
from engine.input import Input

class MiScript(BaseScript):
    def on_start(self, entity, world):
        self.velocidad = 5.0

    def on_update(self, entity, world, dt):
        from engine.components import Transform
        tr = world.get_component(entity, Transform)
        if Input.get_key("W"):
            tr.position[2] -= self.velocidad * dt

    def on_collision(self, entity, other_entity, world):
        print(f"Colisión: {entity} <-> {other_entity}")
```

### Estructura del proyecto

```
Aether3D/
├── engine/
│   ├── ecs/                  # World, System base
│   ├── components/           # Transform, MeshRenderer, Material, Camera,
│   │                         # Rigidbody, Collider, Script, ParticleEmitter
│   ├── systems/              # RenderSystem, PhysicsSystem, ScriptSystem
│   ├── rendering/            # Shader, Mesh, OrbitCamera, Skybox, ShadowMap,
│   │                         # PostProcess, ParticleSystem, IBL, MaterialRegistry
│   ├── scene/                # Serializer (JSON)
│   ├── scripting/            # BaseScript
│   ├── gizmo.py              # Gizmos de transformación
│   ├── picking.py            # Ray casting
│   └── input.py              # Singleton Input para scripts
├── editor/
│   ├── viewport.py           # QOpenGLWidget — loop de render + sistemas
│   ├── main_window.py        # Ventana principal, toolbar, menús
│   ├── inspector.py          # Panel de componentes dinámico
│   └── hierarchy_tree.py     # Árbol de escena con drag & drop
├── shaders/                  # GLSL: pbr, basic, grid, skybox, outline,
│   │                         # depth, flat, post, particles
├── assets/
│   ├── materials/            # Presets JSON de materiales PBR
│   ├── models/               # Modelos .obj
│   ├── particles/            # Presets JSON de emisores
│   ├── scripts/              # Scripts de usuario
│   └── skyboxes/             # Cubemaps (space, sky)
├── requirements.txt
└── main.py                   # Escena de prueba y punto de entrada
```

---

## Componentes disponibles

| Componente | Descripción |
|------------|-------------|
| `Transform` | Posición, rotación (Euler XYZ°), escala, jerarquía padre-hijo |
| `MeshRenderer` | Mesh (cube/sphere/plane/capsule/obj), color, visible |
| `Material` | Albedo, metallic, roughness, emission, mapas de textura (PBR) |
| `Camera` | FOV, near/far, proyección perspectiva/ortográfica, `is_main` |
| `Rigidbody` | Masa, restitución, fricción, gravedad, estático/dinámico |
| `Collider` | AABB o Sphere, tamaño/radio, offset |
| `Script` | Ruta a archivo `.py` con clase `BaseScript` |
| `ParticleEmitter` | Emisión, vida, velocidad, tamaño, color, forma, burst |

---

## Dependencias

| Librería | Versión | Uso |
|----------|---------|-----|
| PyQt6 | ≥ 6.5 | Ventana, widgets, contexto OpenGL |
| PyOpenGL | ≥ 3.1.7 | Bindings OpenGL 3.3 Core |
| numpy | ≥ 1.24 | Matemáticas vectoriales y matriciales |
| pyrr | ≥ 0.10.3 | Matrices row-major (look_at, perspective) |
| Pillow | ≥ 10.0 | Carga de texturas e imágenes de skybox |

---

## Notas técnicas

- **FBOs via Qt** — `QOpenGLFramebufferObject` en lugar de `glGenFramebuffers` directos para evitar fallos de carga de extensiones en PyOpenGL sobre Windows.
- **IBL sin FBO** — la convolución del irradiance cubemap se ejecuta en CPU con numpy (256 muestras coseno-ponderadas por texel) para obviar por completo el problema anterior.
- **Matrices row-major** — pyrr usa convención `v @ M`; la translación está en `wm[3, :3]`.
- **Shadow map GL_R32F** — el depth se almacena como textura de color `GL_R32F` (no como `GL_DEPTH_COMPONENT`) debido a las restricciones del FBO de Qt.
- **Stride de mesh 32 bytes** — el formato interno es `[pos3, normal3, uv2]`; los shaders que no usan UV siguen funcionando porque leen en los mismos offsets 0 y 12.
- **Contorno sin stencil** — se inflan las normales con `GL_CULL_FACE_FRONT`; el stencil buffer se descartó porque colisionaba con el sistema de ray picking.
