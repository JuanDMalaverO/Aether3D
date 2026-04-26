#version 330 core

in vec3 vNormal;
in vec3 vFragPos;
in vec4 vFragPosLightSpace;

uniform vec3 uColor;
uniform vec3 uLightDir;
uniform vec3 uViewPos;

// Shadow map
uniform sampler2D uShadowMap;
uniform float     uShadowBias;
uniform int       uShadowEnabled;   // 1 = activo, 0 = desactivado

out vec4 FragColor;

// PCF 3×3: promedia 9 muestras para suavizar bordes de sombra
float shadowPCF(vec4 fragPosLightSpace, vec3 normal, vec3 lightDir) {
    // División de perspectiva → NDC [-1,1]
    vec3 proj = fragPosLightSpace.xyz / fragPosLightSpace.w;
    // Remapear a [0,1] para samplear la textura
    proj = proj * 0.5 + 0.5;

    // Fragmentos fuera del frustum de la luz → sin sombra
    if (proj.z > 1.0 || proj.x < 0.0 || proj.x > 1.0 ||
                         proj.y < 0.0 || proj.y > 1.0)
        return 0.0;

    float currentDepth = proj.z;

    // Bias adaptativo: mayor cuando la normal es tangente a la luz (más acne)
    float adaptBias = max(0.05 * (1.0 - dot(normalize(normal), normalize(-lightDir))),
                          uShadowBias);

    float shadow    = 0.0;
    vec2  texelSize = 1.0 / vec2(textureSize(uShadowMap, 0));
    for (int x = -1; x <= 1; ++x) {
        for (int y = -1; y <= 1; ++y) {
            float pcfDepth = texture(uShadowMap,
                                     proj.xy + vec2(x, y) * texelSize).r;
            shadow += (currentDepth - adaptBias > pcfDepth) ? 1.0 : 0.0;
        }
    }
    return shadow / 9.0;
}

void main() {
    vec3 normal   = normalize(vNormal);
    vec3 lightDir = normalize(-uLightDir);

    // Ambient
    vec3 ambient = 0.25 * uColor;

    // Diffuse
    float diff   = max(dot(normal, lightDir), 0.0);
    vec3  diffuse = diff * uColor;

    // Specular (Blinn-Phong)
    vec3  viewDir  = normalize(uViewPos - vFragPos);
    vec3  halfDir  = normalize(lightDir + viewDir);
    float spec     = pow(max(dot(normal, halfDir), 0.0), 32.0);
    vec3  specular = vec3(0.3) * spec;

    // Sombra
    float shadow = (uShadowEnabled == 1)
                   ? shadowPCF(vFragPosLightSpace, normal, uLightDir)
                   : 0.0;

    vec3 result = ambient + (1.0 - shadow) * (diffuse + specular);
    FragColor   = vec4(result, 1.0);
}
