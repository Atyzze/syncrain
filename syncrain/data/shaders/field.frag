// Pass 2 (uCols x uRows): soft brightness field around the streams, sampled with bilinear filtering
// later for the dark "veil" behind each stream and the wide glow.
uniform sampler2D uState;
uniform int uCols, uRows;
out vec4 oField;

void main() {
    ivec2 p = ivec2(gl_FragCoord.xy);
    vec3 acc = vec3(0.0);
    float wsum = 0.0;
    for (int dy = -2; dy <= 2; dy++) {
        for (int dx = -2; dx <= 2; dx++) {
            float w = exp(-0.5 * float(dx * dx + dy * dy) / 1.1);
            wsum += w;
            ivec2 q = p + ivec2(dx, dy);
            if (q.x < 0 || q.y < 0 || q.x >= uCols || q.y >= uRows) continue;
            vec4 s = texelFetch(uState, q, 0);
            acc += w * vec3(s.r, s.g, s.r * 0.75 + s.g);
        }
    }
    oField = vec4(acc / wsum, 1.0);
}
