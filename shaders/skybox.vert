#version 330 core

layout(location = 0) in vec3 aPos;

out vec3 vTexCoords;

uniform mat4 uView;
uniform mat4 uProjection;

void main() {
    // El vector de posición del cubo es el selector del cubemap
    vTexCoords = aPos;

    // Eliminamos la traslación de la vista: el skybox siempre envuelve la cámara
    mat4 viewNoTrans = mat4(mat3(uView));

    // z = w  →  tras la división de perspectiva z/w = 1.0 (fondo máximo).
    // Con GL_LEQUAL el skybox "rellena" solo los píxeles vacíos.
    vec4 pos = uProjection * viewNoTrans * vec4(aPos, 1.0);
    gl_Position = pos.xyww;
}
