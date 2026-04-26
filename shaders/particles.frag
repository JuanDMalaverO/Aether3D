#version 330 core

in vec4 vColor;
in vec2 vUV;

out vec4 FragColor;

void main() {
    // Borde suave circular
    vec2  uv   = vUV - 0.5;
    float dist = length(uv) * 2.0;        // 0 en el centro, 1 en el borde
    float alpha = 1.0 - smoothstep(0.5, 1.0, dist);

    FragColor = vec4(vColor.rgb, vColor.a * alpha);
}
