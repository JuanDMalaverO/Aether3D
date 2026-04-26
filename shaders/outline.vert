#version 330 core

layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform float uOutlineWidth;

void main() {
    // Inflamos en espacio mundo para que la anchura sea uniforme
    // independientemente del scale no uniforme del objeto.
    vec4 worldPos = uModel * vec4(aPos, 1.0);
    vec3 worldNormal = normalize(mat3(transpose(inverse(uModel))) * aNormal);
    worldPos.xyz += worldNormal * uOutlineWidth;
    gl_Position = uProjection * uView * worldPos;
}
