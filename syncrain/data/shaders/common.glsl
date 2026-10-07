// ---------------------------------------------------------------------------------------------
// syncrain: shared definitions. Everything on screen is a pure function of
//   (uSec, uFrac)  wall-clock time: whole seconds since 2024-01-01T00:00:00Z plus the fraction
//   uSeed          the channel (FNV-1a hash of its name)
// so any machine with a synced clock renders the identical frame, and nothing ever loops.
// Randomness comes only from integer hashing (bit-exact on every GPU); floats are only used for
// small, local quantities such as "seconds since this drop spawned".
// ---------------------------------------------------------------------------------------------
uniform uint uSec;
uniform float uFrac;
uniform uint uSeed;

uint lowbias32(uint x) {                       // Chris Wellons' lowbias32 integer hash
    x ^= x >> 16; x *= 0x7feb352du;
    x ^= x >> 15; x *= 0x846ca68bu;
    x ^= x >> 16;
    return x;
}
uint H(uint a, uint b, uint c, uint salt) {
    return lowbias32(uSeed ^ lowbias32(a ^ lowbias32(b ^ lowbias32(c ^ (salt * 0x9e3779b9u)))));
}
float U(uint h) { return float(h >> 8) * (1.0 / 16777216.0); }   // uniform in [0, 1)

// seconds into the current hour; periodic effects use whole cycles per hour so they stay continuous
float hourTime() { return float(uSec % 3600u) + uFrac; }
float cyclesPerHour(float n) { return fract(n * (hourTime() / 3600.0)); }
