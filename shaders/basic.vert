#version 330 core

layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform mat4 uLightSpaceMatrix;

out vec3 vNormal;
out vec3 vFragPos;
out vec4 vFragPosLightSpace;

void main() {
    vec4 worldPos = uModel * vec4(aPos, 1.0);
    vFragPos            = worldPos.xyz;
    vNormal             = mat3(transpose(inverse(uModel))) * aNormal;
    vFragPosLightSpace  = uLightSpaceMatrix * worldPos;
    gl_Position         = uProjection * uView * worldPos;
}
