#version 330 core

in vec3 vFragPos;
in vec3 vNormal;
in vec2 vTexCoord;
in vec4 vFragPosLightSpace;

out vec4 FragColor;

// Material
uniform vec3  uAlbedo;
uniform float uMetallic;
uniform float uRoughness;
uniform vec3  uEmission;
uniform float uEmissionStrength;

uniform sampler2D uAlbedoMap;
uniform sampler2D uNormalMap;
uniform sampler2D uMetallicRoughnessMap;
uniform sampler2D uAoMap;
uniform int uHasAlbedoMap;
uniform int uHasNormalMap;
uniform int uHasMetallicRoughnessMap;
uniform int uHasAoMap;

// IBL
uniform samplerCube uIrradianceMap;
uniform samplerCube uPrefilterMap;
uniform int uIBLEnabled;

// Luz + cámara
uniform vec3 uLightDir;
uniform vec3 uViewPos;

// Sombra
uniform sampler2D uShadowMap;
uniform mat4      uLightSpaceMatrix;
uniform float     uShadowBias;
uniform int       uShadowEnabled;

const float PI = 3.14159265359;

float DistributionGGX(float NdotH, float a) {
    float a2 = a * a;
    float d = NdotH * NdotH * (a2 - 1.0) + 1.0;
    return a2 / (PI * d * d + 1e-7);
}

float GeometrySchlickGGX(float NdotX, float roughness) {
    float r = roughness + 1.0;
    float k = (r * r) / 8.0;
    return NdotX / (NdotX * (1.0 - k) + k + 1e-7);
}

float GeometrySmith(float NdotV, float NdotL, float roughness) {
    return GeometrySchlickGGX(max(NdotV, 0.0), roughness)
         * GeometrySchlickGGX(max(NdotL, 0.0), roughness);
}

vec3 FresnelSchlick(float cosTheta, vec3 F0) {
    return F0 + (1.0 - F0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
}

vec3 FresnelSchlickRoughness(float cosTheta, vec3 F0, float roughness) {
    return F0 + (max(vec3(1.0 - roughness), F0) - F0)
              * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
}

// Aproximacion BRDF de Lagarde & de Rousiers — sin necesidad de textura LUT
vec2 BRDFApprox(float roughness, float NdotV) {
    vec4 c0 = vec4(-1.0, -0.0275, -0.572,  0.022);
    vec4 c1 = vec4( 1.0,  0.0425,  1.040, -0.040);
    vec4 r  = roughness * c0 + c1;
    float a004 = min(r.x * r.x, exp2(-9.28 * NdotV)) * r.x + r.y;
    return vec2(-1.04, 1.04) * a004 + r.zw;
}

float ShadowPCF(vec4 fragPosLS, float NdotL) {
    if (uShadowEnabled == 0) return 0.0;
    vec3 proj = fragPosLS.xyz / fragPosLS.w * 0.5 + 0.5;
    if (proj.z > 1.0 || any(lessThan(proj.xy, vec2(0.0))) || any(greaterThan(proj.xy, vec2(1.0))))
        return 0.0;
    float bias = max(uShadowBias * (1.0 - NdotL), uShadowBias * 0.1);
    float shadow = 0.0;
    vec2 ts = 1.0 / vec2(textureSize(uShadowMap, 0));
    for (int x = -1; x <= 1; x++)
        for (int y = -1; y <= 1; y++)
            shadow += (proj.z - bias > texture(uShadowMap, proj.xy + vec2(x,y)*ts).r) ? 1.0 : 0.0;
    return shadow / 9.0;
}

void main() {
    // --- Muestrear material ---
    vec3  albedo    = uAlbedo;
    if (uHasAlbedoMap != 0)
        albedo = pow(texture(uAlbedoMap, vTexCoord).rgb, vec3(2.2));

    float metallic  = uMetallic;
    float roughness = max(uRoughness, 0.04);
    if (uHasMetallicRoughnessMap != 0) {
        vec2 mr = texture(uMetallicRoughnessMap, vTexCoord).rg;
        metallic = mr.r;  roughness = max(mr.g, 0.04);
    }

    float ao = 1.0;
    if (uHasAoMap != 0) ao = texture(uAoMap, vTexCoord).r;

    // --- Normal ---
    vec3 N = normalize(vNormal);
    if (uHasNormalMap != 0) {
        // TBN basado en derivadas (sin buffer de tangentes)
        vec3 dp1 = dFdx(vFragPos),  dp2 = dFdy(vFragPos);
        vec2 uv1 = dFdx(vTexCoord), uv2 = dFdy(vTexCoord);
        float det = uv1.x * uv2.y - uv1.y * uv2.x;
        if (abs(det) > 1e-7) {
            vec3 T = normalize(( dp1 * uv2.y - dp2 * uv1.y) / det);
            vec3 B = normalize((-dp1 * uv2.x + dp2 * uv1.x) / det);
            vec3 nmap = texture(uNormalMap, vTexCoord).rgb * 2.0 - 1.0;
            N = normalize(mat3(T, B, N) * nmap);
        }
    }

    vec3  V    = normalize(uViewPos - vFragPos);
    float NdotV = clamp(dot(N, V), 0.0, 1.0);
    vec3  R    = reflect(-V, N);

    vec3 F0 = mix(vec3(0.04), albedo, metallic);

    // --- Luz direccional ---
    vec3 Lo = vec3(0.0);
    {
        vec3  L     = normalize(-uLightDir);
        vec3  H     = normalize(V + L);
        float NdotL = max(dot(N, L), 0.0);
        float NdotH = max(dot(N, H), 0.0);
        float HdotV = max(dot(H, V), 0.0);

        float D = DistributionGGX(NdotH, roughness * roughness);
        float G = GeometrySmith(NdotV, NdotL, roughness);
        vec3  F = FresnelSchlick(HdotV, F0);

        vec3 spec    = D * G * F / max(4.0 * NdotV * NdotL, 0.001);
        vec3 kD      = (1.0 - F) * (1.0 - metallic);
        float shadow = ShadowPCF(vFragPosLightSpace, NdotL);
        Lo += (kD * albedo / PI + spec) * NdotL * (1.0 - shadow) * 3.0;
    }

    // --- IBL ---
    vec3 ambient;
    if (uIBLEnabled != 0) {
        vec3 kS = FresnelSchlickRoughness(NdotV, F0, roughness);
        vec3 kD = (1.0 - kS) * (1.0 - metallic);

        vec3 irradiance = texture(uIrradianceMap, N).rgb;
        vec3 diffuse    = kD * irradiance * albedo;

        float maxLOD = 4.0;
        vec3 prefilteredColor = textureLod(uPrefilterMap, R, roughness * maxLOD).rgb;
        vec2 brdf = BRDFApprox(roughness, NdotV);
        vec3 specular = prefilteredColor * (kS * brdf.x + brdf.y);

        ambient = (diffuse + specular) * ao;
    } else {
        ambient = vec3(0.03) * albedo * ao;
    }

    // --- Color final (HDR lineal — el post-procesado aplica tonemapping) ---
    vec3 color = ambient + Lo + uEmission * uEmissionStrength;
    FragColor = vec4(color, 1.0);
}
