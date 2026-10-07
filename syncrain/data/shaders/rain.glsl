// Crisp glyph colour for a screen pixel (used at full resolution and, for the bloom source, at 1/4).
uniform int uCols, uRows;
uniform float uCell;         // cell size in pixels
uniform float uColOffset;    // first visible column (narrow screens show the middle of the 64-column stream)
uniform sampler2D uState;
uniform sampler2D uAtlas;    // 16 x 16 slots, each covering 1.5 x 1.5 cells, glyph centred
uniform vec3 cDeep, cMid, cPale, cHead;
uniform int uContrast;

vec4 cellState(ivec2 c) {
    if (c.x < 0 || c.y < 0 || c.x >= uCols || c.y >= uRows) return vec4(0.0);
    return texelFetch(uState, c, 0);
}

// px: pixel position in full-resolution screen pixels, origin top-left
vec3 rainGlyph(vec2 px, float cell) {
    vec2 pc = px / cell + vec2(uColOffset, 0.0);
    vec2 gdx = dFdx(pc) * (1.0 / 24.0), gdy = dFdy(pc) * (1.0 / 24.0);   // explicit gradients: no seams at cell edges
    ivec2 ci = ivec2(floor(pc));
    vec4 st = cellState(ci);
    if (st.r < 0.003) return vec3(0.0);
    vec2 f = pc - vec2(ci);
    int gi = int(st.b * 255.0 + 0.5);
    vec2 auv = (vec2(float(gi % 16), float(gi / 16)) + (f + 0.25) / 1.5) / 16.0;
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
    return g * (B * (1.0 - whiteCut * W) * ramp + W * cHead);
}
