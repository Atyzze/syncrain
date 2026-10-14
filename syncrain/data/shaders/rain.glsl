// Crisp glyph colour for a screen pixel (used at full resolution and, for the bloom source, at 1/4).
uniform int uCols, uRows;
uniform float uCell;         // cell size in pixels
uniform float uColOffset;    // first visible column (narrow screens show the middle of the 64-column stream)
uniform sampler2D uState;
uniform sampler2D uAtlas;    // 16 slots a row, uAtlasRows rows, each covering 1.5 x 1.5 cells, glyph centred
uniform int uAtlasRows;
uniform vec3 cDeep, cMid, cPale, cHead;
uniform int uContrast;
uniform int uFlavours;       // colours at once: each column one of this many hues round the wheel (1: as given)
uniform int uFlavourWave;    // 1: the hues follow the columns in order, a rainbow across the stream; 0: by hash

vec4 cellState(ivec2 c) {
    if (c.x < 0 || c.y < 0 || c.x >= uCols || c.y >= uRows) return vec4(0.0);
    return texelFetch(uState, c, 0);
}

// A column's turn of the hue wheel. By the channel's hash the columns are as the stream's, the same
// on every machine; as a wave they go round the wheel once across the 64 columns.
float flavourTurns(int col) {
    if (uFlavours <= 1) return 0.0;
    int k = uFlavourWave == 1 ? (((col % uCols) + uCols) % uCols) * uFlavours / uCols
                              : int(H(uint(col), 0u, 0u, 90u) % uint(uFlavours));
    return float(k) / float(uFlavours);
}

// px: pixel position in full-resolution screen pixels, origin top-left
vec3 rainGlyph(vec2 px, float cell) {
    vec2 pc = px / cell + vec2(uColOffset, 0.0);
    vec2 grid = vec2(16.0, float(uAtlasRows));
    vec2 gdx = dFdx(pc) / (1.5 * grid), gdy = dFdy(pc) / (1.5 * grid);   // explicit gradients: no seams at cell edges
    ivec2 ci = ivec2(floor(pc));
    vec4 st = cellState(ci);
    if (st.r < 0.003) return vec3(0.0);
    vec2 f = pc - vec2(ci);
    int gi = int(st.b * 255.0 + 0.5) + 256 * int(st.a * 255.0 + 0.5);
    vec2 auv = (vec2(float(gi % 16), float(gi / 16)) + (f + 0.25) / 1.5) / grid;
    float g = textureGrad(uAtlas, auv, gdx, gdy).r;
    float B = st.r, W = st.g;
    vec3 ramp = cMid;
    float whiteCut = 0.6;
    if (uContrast == 1) {                    // deep -> mid -> pale with brightness
        float wd = 1.0 - smoothstep(0.08, 0.42, B);
        float wp = smoothstep(0.62, 1.0, B);
        ramp = wd * cDeep + max(0.0, 1.0 - wd - wp) * cMid + wp * cPale;
        whiteCut = 0.55;
    }
    vec3 c = g * (B * (1.0 - whiteCut * W) * ramp + W * cHead);
    float t = flavourTurns(ci.x);
    return t > 0.0 ? max(hueRotate(c, t), 0.0) : c;
}
