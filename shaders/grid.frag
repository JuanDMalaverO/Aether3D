#version 330 core

in vec3 vNearPoint;
in vec3 vFarPoint;

uniform mat4 uView;
uniform mat4 uProjection;

out vec4 FragColor;

// Dibuja una grilla con ejes X (rojo) y Z (azul) resaltados
vec4 grid(vec3 worldPos, float scale) {
    vec2 coord = worldPos.xz * scale;
    vec2 derivative = fwidth(coord);
    vec2 g = abs(fract(coord - 0.5) - 0.5) / derivative;
    float line = min(g.x, g.y);
    float minZ = min(derivative.y, 1.0);
    float minX = min(derivative.x, 1.0);

    vec4 color = vec4(0.35, 0.35, 0.35, 1.0 - min(line, 1.0));

    // Eje Z (mundo z=0) → línea roja (X axis en convención Y-up)
    if (worldPos.x > -minX && worldPos.x < minX)
        color = vec4(0.2, 0.4, 1.0, color.a);
    // Eje X (mundo x=0) → línea azul
    if (worldPos.z > -minZ && worldPos.z < minZ)
        color = vec4(1.0, 0.3, 0.3, color.a);

    return color;
}

float computeDepth(vec3 pos) {
    vec4 clip = uProjection * uView * vec4(pos, 1.0);
    return (clip.z / clip.w) * 0.5 + 0.5;
}

float computeLinearDepth(vec3 pos) {
    vec4 clip = uProjection * uView * vec4(pos, 1.0);
    float clipDepth = (clip.z / clip.w);   // [-1,1]
    // Near y far fijos para fade, ajustar si se quiere
    float near = 0.1;
    float far = 100.0;
    float linearDepth = (2.0 * near * far) / (far + near - clipDepth * (far - near));
    return linearDepth / far;
}

void main() {
    // Intersección del rayo near->far con el plano Y=0
    float t = -vNearPoint.y / (vFarPoint.y - vNearPoint.y);
    if (t < 0.0) discard;

    vec3 worldPos = vNearPoint + t * (vFarPoint - vNearPoint);

    gl_FragDepth = computeDepth(worldPos);

    float linearDepth = computeLinearDepth(worldPos);
    float fade = max(0.0, 0.5 - linearDepth);

    vec4 g1 = grid(worldPos, 1.0);
    vec4 g10 = grid(worldPos, 0.1) * 0.5;
    vec4 color = g1 + g10;
    color.a *= fade;
    if (color.a < 0.01) discard;
    FragColor = color;
}
