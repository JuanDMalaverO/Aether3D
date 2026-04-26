#version 330 core

// Grid infinito técnica de Marie's Tricks / basado en el método de ray-plane
// Dibujamos un quad que cubre el plano Y=0 usando unprojection.

layout(location = 0) in vec3 aPos;

uniform mat4 uView;
uniform mat4 uProjection;

out vec3 vNearPoint;
out vec3 vFarPoint;

// Desproyecta un punto NDC al mundo
vec3 unproject(float x, float y, float z, mat4 view, mat4 proj) {
    mat4 invVP = inverse(proj * view);
    vec4 p = invVP * vec4(x, y, z, 1.0);
    return p.xyz / p.w;
}

void main() {
    // aPos viene como quad en NDC (x,y en [-1,1], z=0)
    vec2 p = aPos.xy;
    vNearPoint = unproject(p.x, p.y, -1.0, uView, uProjection);  // near plane
    vFarPoint  = unproject(p.x, p.y,  1.0, uView, uProjection);  // far plane
    gl_Position = vec4(aPos.xy, 0.0, 1.0);
}
