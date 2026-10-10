// Pass 1 (one fragment per rain cell, uCols x uRows): brightness, head whiteness and glyph of every cell.
//
// Drops: every column gets one spawn opportunity per second. Whether a drop spawns, and all of its
// parameters, come from H(column, second). A cell's state is the brightest of all drops that could
// still be visible, so it only needs to look back over the lifetime of the slowest drop.
//#include common

uniform int uCols, uRows;
uniform sampler2D uLUT;      // 256 x 1: weighted glyph table (R = glyph index / 255)
uniform sampler2D uWords;    // 16 x n: hidden words, one per row (R = glyph index / 255, 255 = end)
uniform int uNumWords;
uniform vec4 uKeep;          // cells kept free of words (the logo): col0, row0, col1, row1
uniform float uDensity;      // spawn probability per column per second
uniform float uSpeed;        // fall speed, times the theme's
uniform float uHiero;        // share of the scrambling and resting glyphs drawn from the hieroglyphs
uniform int uHieroFirst, uHieroCount;   // where the hieroglyphs sit in the atlas
uniform float uWordRate;     // chance that a full-height drop carries a word
uniform float uGlintRate;    // chance per cell per 2 s of a brief flare-up
uniform int uContrast;       // 1: wide brightness range (dim distant streams, hot heads, glints)
out vec4 oState;

int lutGlyph(uint h) {
    if (U(lowbias32(h ^ 0x68696572u)) < uHiero) return uHieroFirst + int(lowbias32(h ^ 0x6f676c79u) % uint(uHieroCount));
    return int(texelFetch(uLUT, ivec2(int(h & 255u), 0), 0).r * 255.0 + 0.5);
}
int wordGlyph(int w, int i) { return int(texelFetch(uWords, ivec2(i, w), 0).r * 255.0 + 0.5); }
int wordLen(int w) {
    int n = 0;
    for (int i = 0; i < 16; i++) { if (wordGlyph(w, i) == 255) break; n++; }
    return n;
}

void main() {
    int c = int(gl_FragCoord.x), r = int(gl_FragCoord.y);     // r counts from the top of the screen
    uint cu = uint(c), ru = uint(r);
    float fr = float(r);

    float B = 0.0, W = 0.0;
    int G = -1;
    bool headCell = false, wordCell = false;

    // longest life: a word drop (7 rows/s at speed 1) crossing the screen plus its 34-row trail
    int back = int(ceil((float(uRows) + 41.0) / (7.0 * uSpeed))) + 1;
    for (int i = 0; i < 256; i++) {
        if (i > back) break;
        uint k = uSec - uint(i);                               // spawn second
        if (U(H(cu, k, 0u, 1u)) >= uDensity) continue;
        float el = float(i) + uFrac - U(H(cu, k, 0u, 2u));      // seconds since spawn
        if (el < 0.0) continue;

        float v  = mix(7.5, 20.8, U(H(cu, k, 0u, 3u)));       // rows per second
        float T  = mix(9.0, 28.0, U(H(cu, k, 0u, 4u)));       // trail length in rows
        float a  = mix(0.6, 1.0, U(H(cu, k, 0u, 5u)));        // brightness
        bool fromTop = U(H(cu, k, 0u, 6u)) < 0.75;
        float r0 = fromTop ? -3.0 * U(H(cu, k, 0u, 7u)) : U(H(cu, k, 0u, 7u)) * 21.6;
        bool runs = U(H(cu, k, 0u, 8u)) < 0.7;                 // runs off the bottom, or stops early
        float r1 = runs ? 1.0e5 : r0 + mix(8.0, 30.0, U(H(cu, k, 0u, 9u)));
        float hw = 1.0;
        int hot = 1;
        if (uContrast == 1) {
            float u = (a - 0.6) / 0.4;
            a = 0.14 + 0.86 * pow(u, 1.7);                     // most streams dim and distant, a few bright
            hw = U(H(cu, k, 0u, 10u)) < 0.2 ? 0.2 : mix(0.6, 1.0, U(H(cu, k, 0u, 11u)));
            int hx = int(U(H(cu, k, 0u, 12u)) * 4.0);          // 1, 1, 2, 3 white cells behind the head
            hot = hx < 2 ? 1 : hx;
        }

        int word = -1, wr = 0, wl = 0;
        if (uNumWords > 0 && fromTop && runs && U(H(cu, k, 0u, 13u)) < uWordRate) {
            int w = int(H(cu, k, 0u, 14u) % uint(uNumWords));
            int L = wordLen(w);
            bool keepCol = float(c) >= uKeep.x && float(c) <= uKeep.z;
            for (int t = 0; t < 4; t++) {
                int cand = 3 + int(U(H(cu, k, uint(t), 15u)) * float(max(1, uRows - L - 6)));
                bool clash = keepCol && float(cand + L) >= uKeep.y && float(cand) <= uKeep.w;
                if (!clash && cand + L <= uRows - 3) { word = w; wr = cand; wl = L; break; }
            }
            if (word >= 0) {
                v = mix(7.0, 10.0, U(H(cu, k, 0u, 16u)));
                T = mix(26.0, 34.0, U(H(cu, k, 0u, 17u)));
                a = 1.0; hw = 1.0; hot = 1;
            }
        }

        v *= uSpeed;
        float head = r0 + v * el;
        bool alive = head <= r1;
        if (r < max(0, int(floor(r0))) || fr > floor(min(head, r1))) continue;
        float age = el - (fr - r0) / v;                         // seconds since the head reached this row
        if (age < 0.0) continue;
        float x = age * v / T;
        if (x >= 1.0) continue;

        float b = pow(1.0 - x, 1.6) * a;
        float w = 0.0;
        int hr = int(floor(head));
        bool isHead = alive && r == hr;
        if (uContrast == 1) {
            if (isHead) { b = 0.4 + 0.6 * a; w = hw; }
            else if (alive) {
                int kb = hr - r;
                if (kb >= 1 && kb <= hot) w = hw * 0.5 * (1.0 - float(kb - 1) / float(hot));
            }
        } else {
            if (isHead) { b = 1.0; w = 1.0; }
            else if (alive && r == hr - 1) w = 0.22;
        }

        if (b > B) {
            B = b; W = max(W, w); headCell = isHead; wordCell = false; G = -1;
            if (word >= 0 && r >= wr && r < wr + wl) {
                G = wordGlyph(word, r - wr);
                wordCell = true;
                B = min(1.0, b * 1.15);
                if (!isHead) W = max(W, 0.28 * b);
            } else if (isHead) {
                uint tick15 = uSec * 15u + uint(uFrac * 15.0);   // the leading glyph scrambles 15x a second
                G = lutGlyph(H(cu, ru, tick15, 20u));
            }
        }
    }

    if (B > 0.0 && !headCell) {                                 // slow per-cell shimmer
        if (uContrast == 1) {
            float n = 800.0 + float(H(cu, ru, 0u, 30u) % 2800u);  // 0.22 .. 1 Hz, in whole cycles per hour
            float amp = mix(0.04, 0.32, U(H(cu, ru, 0u, 31u)));
            float ph = U(H(cu, ru, 0u, 32u));
            B *= 1.0 - amp * (0.5 + 0.5 * sin(6.2831853 * (cyclesPerHour(n) + ph)));
        } else {
            float n = float(1700u + H(cu, ru, 0u, 30u) % 3600u);
            B *= 0.86 + 0.14 * sin(6.2831853 * (cyclesPerHour(n) + U(H(cu, ru, 0u, 32u))));
        }
    }

    if (uContrast == 1 && B > 0.08) {                           // glints: random flare-ups inside living streams
        uint gs = uSec / 2u;
        for (int j = 0; j < 2; j++) {
            uint s = gs - uint(j);
            if (U(H(cu, ru, s, 40u)) < uGlintRate) {
                float start = 2.0 * U(H(cu, ru, s, 41u));
                float dur = mix(0.18, 0.6, U(H(cu, ru, s, 42u)));
                float pk = mix(0.75, 1.0, U(H(cu, ru, s, 43u)));
                float tau = float(uSec - s * 2u) + uFrac - start;
                if (tau >= 0.0 && tau < dur) {
                    float e = pk * pow(1.0 - tau / dur, 1.5);
                    B = max(B, e); W = max(W, 0.6 * e);
                }
            }
        }
    }

    if (B > 0.015 && G < 0) {                                   // resting glyph, re-rolled every 1.5 .. 6 s
        uint tick4 = uSec * 4u + uint(uFrac * 4.0);
        uint P = 6u + H(cu, ru, 0u, 50u) % 19u;
        uint ph = H(cu, ru, 0u, 51u) % P;
        G = lutGlyph(H(cu, ru, (tick4 + ph) / P, 52u));
    }

    oState = vec4(B, W, float(max(G, 0)) / 255.0, wordCell ? 1.0 : 0.0);
}
