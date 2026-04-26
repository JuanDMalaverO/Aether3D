#version 330 core

in vec2 vTexCoord;

uniform sampler2D uScene;
uniform vec2      uTexelSize;        // 1/width, 1/height
uniform int       uTonemap;
uniform float     uExposure;
uniform int       uVignette;
uniform float     uVignetteIntensity;
uniform int       uFXAA;

out vec4 FragColor;

// ── FXAA (simplificado, basado en FXAA 3.11 de Timothy Lottes) ─────────────
// Opera sobre la textura HDR antes del tonemapping.
// Necesita GL_LINEAR en la textura de entrada para muestreo bilineal.
vec3 fxaa() {
    const vec3 toLuma = vec3(0.299, 0.587, 0.114);

    vec3 rgbNW = texture(uScene, vTexCoord + vec2(-1.0, -1.0) * uTexelSize).rgb;
    vec3 rgbNE = texture(uScene, vTexCoord + vec2( 1.0, -1.0) * uTexelSize).rgb;
    vec3 rgbSW = texture(uScene, vTexCoord + vec2(-1.0,  1.0) * uTexelSize).rgb;
    vec3 rgbSE = texture(uScene, vTexCoord + vec2( 1.0,  1.0) * uTexelSize).rgb;
    vec3 rgbM  = texture(uScene, vTexCoord).rgb;

    float lumaNW = dot(rgbNW, toLuma);
    float lumaNE = dot(rgbNE, toLuma);
    float lumaSW = dot(rgbSW, toLuma);
    float lumaSE = dot(rgbSE, toLuma);
    float lumaM  = dot(rgbM,  toLuma);

    float lumaMin   = min(lumaM, min(min(lumaNW, lumaNE), min(lumaSW, lumaSE)));
    float lumaMax   = max(lumaM, max(max(lumaNW, lumaNE), max(lumaSW, lumaSE)));
    float lumaRange = lumaMax - lumaMin;

    // Sin borde significativo → no aplicar AA
    if (lumaRange < max(0.0312, lumaMax * 0.125))
        return rgbM;

    // Dirección del gradiente perpendicular al borde
    vec2 dir;
    dir.x = -((lumaNW + lumaNE) - (lumaSW + lumaSE));
    dir.y =  ((lumaNW + lumaSW) - (lumaNE + lumaSE));

    float dirReduce = max((lumaNW + lumaNE + lumaSW + lumaSE) * (0.25 * 0.0625),
                          1.0 / 128.0);
    float rcpDirMin = 1.0 / (min(abs(dir.x), abs(dir.y)) + dirReduce);
    dir = clamp(dir * rcpDirMin, vec2(-8.0), vec2(8.0)) * uTexelSize;

    // Dos pasadas de muestreo a lo largo del borde
    vec3 rgbA = 0.5 * (
        texture(uScene, vTexCoord + dir * (1.0/3.0 - 0.5)).rgb +
        texture(uScene, vTexCoord + dir * (2.0/3.0 - 0.5)).rgb);
    vec3 rgbB = rgbA * 0.5 + 0.25 * (
        texture(uScene, vTexCoord + dir * -0.5).rgb +
        texture(uScene, vTexCoord + dir *  0.5).rgb);

    float lumaB = dot(rgbB, toLuma);
    return (lumaB < lumaMin || lumaB > lumaMax) ? rgbA : rgbB;
}

// ── Tonemapping ACES filmic ────────────────────────────────────────────────
// Aproximación de la curva ACES (Academy Color Encoding System).
// Comprime valores HDR > 1 con un S-curve en lugar de recortarlos.
vec3 aces(vec3 x) {
    x *= uExposure;
    const float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

// ── Main ──────────────────────────────────────────────────────────────────
void main() {
    // 1. Sample (con o sin FXAA)
    vec3 color = (uFXAA == 1) ? fxaa() : texture(uScene, vTexCoord).rgb;

    // 2. Tonemapping + gamma
    if (uTonemap == 1) {
        color = aces(color);
        // Corrección gamma sRGB (la escena trabaja en espacio lineal).
        color = pow(clamp(color, 0.0, 1.0), vec3(1.0 / 2.2));
    }

    // 3. Viñeta (sobre el color final LDR)
    if (uVignette == 1) {
        vec2 uv   = vTexCoord - 0.5;             // [-0.5, 0.5]
        float vig = 1.0 - dot(uv, uv) * uVignetteIntensity * 4.0;
        color    *= clamp(vig, 0.0, 1.0);
    }

    FragColor = vec4(color, 1.0);
}
