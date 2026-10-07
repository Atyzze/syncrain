// Pass 3 (quarter resolution): glyph layer used only as the bloom source.
//#include common
//#include rain
uniform vec2 uRes;       // full-resolution size
uniform vec2 uTarget;    // this pass's size
out vec4 oGlyph;

void main() {
    vec2 px = vec2(gl_FragCoord.x, uTarget.y - gl_FragCoord.y) * (uRes / uTarget);
    vec3 col = rainGlyph(px, uCell);
    oGlyph = vec4(col * 0.5, 1.0);           // stored at half scale for headroom in 8 bits
}
