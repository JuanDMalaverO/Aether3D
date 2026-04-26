#version 330 core
// Escribe la profundidad en ventana al canal R de la textura GL_R32F.
// El depth renderbuffer del FBO sigue manejando el depth test entre objetos.
out float FragDepth;
void main() {
    FragDepth = gl_FragCoord.z;
}
