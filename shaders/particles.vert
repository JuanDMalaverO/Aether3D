#version 330 core

// ── Por vértice: las 4 esquinas del quad unitario ────────────────────────
layout(location = 0) in vec2  aQuadPos;     // (-0.5,-0.5) … (0.5,0.5)

// ── Por instancia: datos de cada partícula ───────────────────────────────
layout(location = 1) in vec3  aPos;         // posición mundo
layout(location = 2) in float aSize;        // tamaño en unidades mundo
layout(location = 3) in vec4  aColor;       // RGBA
layout(location = 4) in float aRot;         // rotación (radianes)

uniform mat4 uView;
uniform mat4 uProjection;
uniform vec3 uCamRight;      // eje derecho de la cámara en espacio mundo
uniform vec3 uCamUp;         // eje arriba de la cámara en espacio mundo

out vec4 vColor;
out vec2 vUV;

void main() {
    // Rotar el quad en el plano de la cámara
    float c = cos(aRot), s = sin(aRot);
    vec2 rotated = vec2(
        aQuadPos.x * c - aQuadPos.y * s,
        aQuadPos.x * s + aQuadPos.y * c
    );

    // Billboard: expandir en el plano perpendicular a la cámara
    vec3 worldPos = aPos
        + uCamRight * rotated.x * aSize
        + uCamUp    * rotated.y * aSize;

    vColor      = aColor;
    vUV         = aQuadPos + 0.5;          // [0, 1]
    gl_Position = uProjection * uView * vec4(worldPos, 1.0);
}
