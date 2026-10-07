// Passes 4-5: separable Gaussian blur of the quarter-resolution glyph layer.
uniform sampler2D uSrc;
uniform vec2 uStep;      // one texel along the blur direction, in uv units
uniform float uSigma;    // in texels
in vec2 vUV;
out vec4 oBlur;

void main() {
    vec4 acc = vec4(0.0);
    float wsum = 0.0;
    for (int i = -8; i <= 8; i++) {
        float w = exp(-0.5 * float(i * i) / (uSigma * uSigma));
        acc += w * texture(uSrc, vUV + uStep * float(i));
        wsum += w;
    }
    oBlur = acc / wsum;
}
