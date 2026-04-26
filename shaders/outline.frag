#version 330 core

uniform vec3 uOutlineColor;

out vec4 FragColor;

void main() {
    FragColor = vec4(uOutlineColor, 1.0);
}
