# Motor 3D

Motor 3D con editor integrado, construido con Python, PyOpenGL y PyQt6.
Arquitectura ECS (Entity Component System), scene graph, y viewport embebido en editor.

## Instalación

```bash
# 1. Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Correr el editor
python main.py
```

## Controles del viewport

- **MMB (click rueda) + arrastrar**: orbitar cámara alrededor del target
- **Shift + MMB + arrastrar**: pan (mover el punto de enfoque)
- **Scroll**: zoom in/out

## Arquitectura

### ECS (Entity Component System)

- **Entidades**: solo IDs (int). Se crean con `world.create_entity(name)`.
- **Componentes**: dataclasses con datos puros (Transform, MeshRenderer, Camera).
- **Sistemas**: lógica que opera sobre componentes (RenderSystem itera Transform + MeshRenderer).

```python
world = World()
entity = world.create_entity("Cube")
world.add_component(entity, Transform(position=np.array([0, 1, 0])))
world.add_component(entity, MeshRenderer(mesh_name="cube", color=np.array([1, 0, 0])))

# Query:
for entity_id, (transform, mesh) in world.query(Transform, MeshRenderer):
    ...
```

### Estructura de carpetas

```
motor3d/
├── engine/
│   ├── ecs/            # World, System
│   ├── components/     # Transform, MeshRenderer, Camera
│   ├── systems/        # RenderSystem
│   └── rendering/      # Shader, Mesh, OrbitCamera
├── shaders/            # GLSL (basic + grid infinito)
├── editor/             # PyQt6 (MainWindow, Viewport)
└── main.py             # Entry point
```

## Roadmap de desarrollo

### ✅ Semana 1 — Cimientos (actual)
- Ventana PyQt6 con viewport OpenGL 3.3 embebido
- ECS funcional con World, Transform, MeshRenderer
- Cámara orbital estilo Blender
- Grid infinito con shader (ray-plane intersection)
- Shader Blinn-Phong con luz direccional
- Primitivas procedurales: cubo, esfera, plano

### 🔲 Semana 2 — Scene graph y assets
- Jerarquía padre-hijo en Transform (propagación de matrices mundo)
- Carga de modelos `.obj` con `trimesh`
- Sistema de materiales con texturas
- Múltiples luces (point lights, spotlights)

### 🔲 Semana 3 — Editor real
- Inspector con edición en vivo de componentes
- Picking (ray casting para seleccionar objetos)
- Gizmos de transformación (mover/rotar/escalar)
- Guardar/cargar escena en JSON

### 🔲 Semana 4 — Pulido técnico
- Shadow mapping (luz direccional)
- Skybox con cubemap
- Post-processing (framebuffer + tonemapping)
- Asset browser

## Notas técnicas

- El grid infinito no usa geometría: renderiza un fullscreen quad y calcula la intersección rayo-plano en el fragment shader. Técnica robusta y visualmente pulida.
- El sistema de shaders cachea uniform locations para evitar `glGetUniformLocation` en cada frame.
- `QOpenGLWidget` crea automáticamente un FBO; no es necesario manejar contextos manualmente.
