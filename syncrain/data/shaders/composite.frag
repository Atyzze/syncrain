// Pass 6 (full resolution): background, snow, veil, glyphs, bloom, logo.
//#include common
//#include rain
uniform vec2 uRes;
uniform vec2 uOrigin;                // viewport origin in window pixels (several monitors in one X11 window)
uniform sampler2D uField, uBloom, uLogo, uBg, uMask;
uniform int uBgMode;                 // 0: procedural gradient, 1: image
uniform int uHasLogo, uHasMask;
uniform vec3 bgTop, bgBot, bgCenter;
uniform float bgVignette;
uniform float uBgGamma, uBgGain;     // image background tone curve (darkens everything except the mask)
uniform vec2 uBgScale, uBgOffset;    // cover-fit of the image
uniform vec3 cGlow, cLogoGlow;
uniform float uBloomK, uVeil, uLogoSize, uLogoGlowK;
uniform int uSnowN;
uniform vec4 uSnowA[4];              // cell (power of two), speed (whole units/s), density, brightness
uniform vec4 uSnowB[4];              // radius min, radius max, sway, star
uniform vec4 uSnowC[4];              // colour, front (1: drawn over everything)
// anti burn-in motion, all derived from the shared clock so every screen stays in sync
uniform float uSpinCph;              // logo revolutions per hour (0: still)
uniform float uLogoHueCph;           // logo rainbow cycles per hour (0: original colours)
uniform float uRainHueCph;           // whole-rain rainbow cycles per hour (0: theme colours)
uniform float uDrift;                // slow orbit of the logo, or pan of an image, in screen heights
in vec2 vUV;
out vec4 oColor;

float segDist(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    return length(pa - ba * clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0));
}

// Six-fold ice crystal: main arms with two pairs of side branches. p is relative to the centre.
float crystal(vec2 p, float rad, float spin, float aa) {
    float r = length(p);
    float a = mod(atan(p.y, p.x) + spin, 1.0471976);   // 60-degree sectors
    a = min(a, 1.0471976 - a);                           // angle to the nearest arm (mirror fold)
    vec2 q = r * vec2(cos(a), sin(a));                   // arm along +x
    vec2 dir = vec2(0.5, 0.8660254);                     // branches leave the arm at 60 degrees
    float d = segDist(q, vec2(0.0), vec2(rad, 0.0));
    d = min(d, segDist(q, vec2(rad * 0.42, 0.0), vec2(rad * 0.42, 0.0) + dir * rad * 0.32));
    d = min(d, segDist(q, vec2(rad * 0.70, 0.0), vec2(rad * 0.70, 0.0) + dir * rad * 0.20));
    float w = max(rad * 0.05, aa * 0.6);
    float shape = 1.0 - smoothstep(w - aa * 0.5, w + aa * 0.5, d);
    float core = 1.0 - smoothstep(rad * 0.13 - aa * 0.5, rad * 0.13 + aa * 0.5, r);
    return max(shape, core);
}

// One snow layer. Units are 1/1080 of the screen height so flakes look the same at any resolution.
// The fall offset is kept in wrapping 32-bit integers so it stays exact forever; with power-of-two
// cells the cell index stays consistent across the wrap.
vec3 snowLayer(int i, vec2 px) {
    vec4 A = uSnowA[i], Bv = uSnowB[i], C = uSnowC[i];
    uint S = uint(A.x);
    float u = uRes.y / 1080.0;
    vec2 q = px / u;
    uint li = uint(i);
    q.x -= Bv.z * sin(6.2831853 * (cyclesPerHour(float(23 + 17 * i)) + 0.37 * float(i)));  // gusts
    uint Vi = uint(A.y);
    float vf = A.y * uFrac;
    uint D = Vi * uSec + uint(floor(vf));
    float fy = fract(q.y) - fract(vf);
    uint Q = uint(floor(q.y)) - D;
    if (fy < 0.0) { fy += 1.0; Q -= 1u; }
    uint j = Q / S;
    float wy = float(Q % S) + fy;
    float qx = q.x + 16384.0;
    uint ii = uint(floor(qx / float(S)));
    float wx = qx - float(ii) * float(S);

    if (U(H(ii, j, li, 60u)) >= A.z) return vec3(0.0);
    float rad = mix(Bv.x, Bv.y, U(H(ii, j, li, 61u)));
    float margin = rad * 2.0 + 3.0;
    float wob = min(margin * 0.6, float(S) * 0.1);
    float room = max(0.0, float(S) - 2.0 * (margin + wob));
    vec2 c = vec2(margin + wob, margin) + vec2(U(H(ii, j, li, 62u)) * room, U(H(ii, j, li, 63u)) * (float(S) - 2.0 * margin));
    c.x += wob * sin(6.2831853 * (cyclesPerHour(float(20u + H(ii, j, li, 64u) % 60u)) + U(H(ii, j, li, 65u))));
    vec2 d = vec2(wx, wy) - c;
    float dist = length(d);
    if (dist > margin) return vec3(0.0);
    float aa = 1.0 / u;                      // one screen pixel, in units
    float inten;
    if (Bv.w > 0.5 && rad > 3.0) {           // ice crystal, slowly turning; front flakes slightly out of focus
        float spin = 6.2831853 * (cyclesPerHour(float(4u + H(ii, j, li, 66u) % 14u)) + U(H(ii, j, li, 67u)));
        inten = crystal(d, rad, spin, aa * (C.w > 0.5 ? 2.2 : 1.0))
              + 0.22 * exp(-dist * dist / (0.72 * rad * rad));
    } else {
        inten = smoothstep(rad + aa * 0.5, rad * 0.2, dist) + 0.25 * exp(-dist * dist / (4.0 * rad * rad));
    }
    return C.rgb * A.w * inten;
}

vec3 hsv2rgb(vec3 c) {
    vec3 p = abs(fract(c.xxx + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
    return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}

// rotate a colour's hue around the grey axis by a fraction of a turn (keeps its brightness)
vec3 hueRotate(vec3 c, float turns) {
    float a = 6.2831853 * turns;
    const vec3 k = vec3(0.57735027);
    float cs = cos(a), sn = sin(a);
    return c * cs + cross(k, c) * sn + k * dot(k, c) * (1.0 - cs);
}

// slow Lissajous orbit (7 and 5 cycles per hour), in screen heights
vec2 driftOffset() {
    return uDrift * vec2(sin(6.2831853 * cyclesPerHour(7.0)), sin(6.2831853 * (cyclesPerHour(5.0) + 0.21)));
}

vec3 softClip(vec3 x) {
    const float k = 0.78;
    return mix(x, k + (1.0 - k) * tanh((x - k) / (1.0 - k)), step(k, x));
}

void main() {
    vec2 px = vec2(gl_FragCoord.x - uOrigin.x, uRes.y - (gl_FragCoord.y - uOrigin.y));   // top-left origin
    vec2 suv = px / uRes;
    float cell = uCell;
    float rainK = 1.0;

    vec3 col;
    if (uBgMode == 1) {
        // zoom in just enough that the slow pan never shows the image edge
        float Z = 1.0 + 2.2 * uDrift;
        vec2 iuv = uBgOffset + 0.5 * uBgScale
                 + ((suv - 0.5) + driftOffset() * vec2(uRes.y / uRes.x, 1.0)) * uBgScale / Z;
        vec3 img = texture(uBg, iuv).rgb;
        float m = uHasMask == 1 ? texture(uMask, iuv).r : 0.0;
        vec3 bright = uLogoHueCph > 0.0 ? max(hueRotate(img, cyclesPerHour(uLogoHueCph)), 0.0) : img;
        col = mix(pow(img, vec3(uBgGamma)) * uBgGain, bright, m);
        rainK = 1.0 - m;
    } else {
        col = mix(bgTop, bgBot, suv.y);
        vec2 d = (px - 0.5 * uRes) / uRes.y;
        vec3 centre = uRainHueCph > 0.0 ? max(hueRotate(bgCenter, cyclesPerHour(uRainHueCph)), 0.0) : bgCenter;
        col += centre * exp(-dot(d, d) / 0.22);
        col *= 1.0 - bgVignette * smoothstep(0.35, 1.2, length(d * vec2(0.85, 1.3)));
        col += (U(lowbias32(uint(px.x) * 73856093u ^ uint(px.y) * 19349663u)) - 0.5) / 255.0;   // anti-banding
    }

    float logoA = 0.0, logoMask = 0.0, logoHalo = 0.0;
    vec3 logoRGB = vec3(0.0), haloCol = cLogoGlow;
    if (uHasLogo == 1) {
        // the logo texture is padded: the snowflake fills its central 2/3
        float size = uLogoSize * uRes.y * 1.5;
        vec2 d = px - (0.5 * uRes + driftOffset() * uRes.y);
        float ang = 6.2831853 * cyclesPerHour(uSpinCph);
        float cs = cos(ang), sn = sin(ang);
        vec2 r = vec2(cs * d.x + sn * d.y, -sn * d.x + cs * d.y);   // screen -> the logo's own turning frame
        vec2 luv = r / size + 0.5;
        if (luv.x >= 0.0 && luv.x <= 1.0 && luv.y >= 0.0 && luv.y <= 1.0) {
            float lod = max(0.0, log2(float(textureSize(uLogo, 0).x) / size));
            vec4 L = textureLod(uLogo, luv, lod);
            logoA = L.a;
            logoRGB = L.rgb;
            logoMask = smoothstep(0.02, 0.3, textureLod(uLogo, luv, lod + 1.5).a);
            logoHalo = textureLod(uLogo, luv, 7.0).a;
            if (uLogoHueCph > 0.0) {
                // rainbow wheel fixed to the arms, flowing round over time; keeps the logo's own shading
                float base = cyclesPerHour(uLogoHueCph);
                float hue = fract(base + atan(r.y, r.x) / 6.2831853);
                float lum = dot(L.rgb, vec3(0.299, 0.587, 0.114));
                logoRGB = hsv2rgb(vec3(hue, 0.7, 1.0)) * min(1.0, lum * 1.12);
                haloCol = hsv2rgb(vec3(base, 0.55, 1.0));
            }
        }
    }
    rainK *= 1.0 - logoMask;

    for (int i = 0; i < 4; i++) {            // snow behind the rain
        if (i >= uSnowN) break;
        if (uSnowC[i].w < 0.5) col += snowLayer(i, px);
    }

    vec4 fl = texture(uField, (px / cell + vec2(uColOffset, 0.0)) / vec2(float(uCols), float(uRows)));
    col *= 1.0 - rainK * uVeil * clamp(fl.r * 1.3, 0.0, 1.0);

    vec3 glyph = rainGlyph(px, cell);
    vec3 bloom = texture(uBloom, vUV).rgb * 2.0;
    vec3 glow = bloom * 0.95 + cGlow * fl.b * 0.09;
    vec3 rain = glyph + glow * uBloomK;
    if (uRainHueCph > 0.0) rain = max(hueRotate(rain, cyclesPerHour(uRainHueCph)), 0.0);
    col += rainK * rain;

    col += haloCol * logoHalo * uLogoGlowK;
    col = mix(col, logoRGB, logoA);

    for (int i = 0; i < 4; i++) {            // snow in front of everything
        if (i >= uSnowN) break;
        if (uSnowC[i].w > 0.5) col += snowLayer(i, px);
    }

    oColor = vec4(softClip(max(col, 0.0)), 1.0);
}
