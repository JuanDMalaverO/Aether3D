#version 330 core

in  vec3 vTexCoords;
out vec4 FragColor;

uniform samplerCube uSkybox;

void main() {
    // Muestreo directo del cubemap, sin iluminación
    FragColor = texture(uSkybox, vTexCoords);
}
