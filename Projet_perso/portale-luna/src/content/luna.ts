import type { Content } from "./types";

// luna — the moon. Private compute for teams that train large models: a black monolith on the lunar plain,
// a low hard sun, the Earth and the stars in a black sky.
const COMMON = /* glsl */ `
const vec3 SUN = vec3(-0.972, 0.118, -0.203);  // low on the left and a little ahead: every stone throws a long shadow toward the right
const vec3 EARTH = vec3(0.3105, 0.3007, -0.9017); // up and to the right of the monolith; out of the picture on a phone, where the headline is
const vec3 SUNLIGHT = vec3(1.0, 0.97, 0.92) * 2.2;
const vec3 DUST = vec3(0.132, 0.126, 0.117);   // how much light the regolith gives back
const float MOON = 1.7374e6;

// Moon dust doesn't shade like chalk: it throws light back toward where it came from, so ground seen at a glancing
// angle is far brighter than ground seen from above, and nothing darkens toward the horizon.
// How far a place on the ground is from the foot of the slab.
float slabDistance(vec2 p) { vec3 l = toLocal(vec3(p.x, 0.0, p.y)); return length(vec2(max(abs(l.x) - uSlab.x * 0.5, 0.0), l.z)); }
// Lumps and hollows in the dust: height and slope. The height map keeps the ones its cells can hold (texel is a
// cell's size there); with foot > 0 this gives the rest instead, down to what a pixel can show.
vec3 lumps(vec2 p, float texel, float foot) {
  vec3 sum = vec3(0.0);
  float len = 7.0, level = smoothstep(0.0, 1.2, slabDistance(p));
  for (int k = 0; k < 11; k++) {
    float held = smoothstep(4.0, 9.0, len / texel), w = foot > 0.0 ? (1.0 - held) * smoothstep(1.5, 4.0, len / foot) : held;
    if (foot > 0.0 ? len < 1.5 * foot : held <= 0.0) break;
    if (w > 0.0) {
      vec3 n = noised(mat2(0.8, 0.6, -0.6, 0.8) * p / len + float(k) * 5.1);
      sum += w * level * (foot > 0.0 ? 0.10 : 0.034) * vec3(len * (n.x - 0.5), n.yz * mat2(0.8, 0.6, -0.6, 0.8));
    }
    len *= 0.45;
  }
  return sum;
}
// And it is brightest seen with the sun behind you, darker the more you look toward the sun (cosg: the cosine of the
// angle between the sun and the eye, seen from the ground).
float dust(float mu0, float mu, float cosg) {
  if (mu0 <= 0.0) return 0.0;
  return (0.3 * mu0 + 1.4 * mu0 / (mu0 + max(mu, 0.02))) * (0.45 + 4.6 * exp(-1.3 * acos(clamp(cosg, -1.0, 1.0))));
}
`;

// The ground, into the height map: a rolling plain, craters of every size from half a kilometre down to what a cell
// of the map can hold (as many small ones per octave as large ones cover the same area, which is how the moon is),
// some fresh and sharp with bright ejecta, most worn soft; rounded massifs beyond four kilometres; the whole of it
// falling away with the moon's curve, so the horizon is two and a half kilometres off.
const GROUND = /* glsl */ `
// One crater at rho = distance / radius: its height / radius, and that height's slope. age 0 is fresh, 1 worn down.
// soft rounds the crest of the rim over that much of the radius.
vec2 crater(float rho, float age, float soft) {
  float D = mix(0.38, 0.07, pow(age, 0.55)), H = mix(0.085, 0.008, age);
  float inv = 1.0 / (rho * rho * rho), x = rho - 1.0, round_ = sqrt(x * x + soft * soft);
  vec2 f = rho < 1.0 ? vec2(H - (D + H) * (1.0 - pow(rho, 2.4)), (D + H) * 2.4 * pow(rho, 1.4)) : H * vec2((inv - 0.0939) / 0.9061, -3.0 * inv / rho / 0.9061);
  float jump = -3.0 * H / 0.9061 - 2.4 * (D + H); // how sharply the slope turns over at the crest
  return f + 0.5 * jump * vec2(round_ - abs(x), x / round_ - sign(x)) * smoothstep(2.2, 1.6, rho);
}

// The smooth part: swells that flatten where the slab stands, and the far massifs.
float rolling(vec2 p) {
  float r = length(p), a = atan(p.x, -p.y);
  float h = smoothstep(3.0, 26.0, r) * 0.7 * (noise(p / 34.0 + 3.0) - 0.5) + smoothstep(15.0, 140.0, r) * 3.4 * (noise(p / 150.0 + 7.0) - 0.5) + smoothstep(120.0, 900.0, r) * 17.0 * (noise(p / 620.0 + 1.0) - 0.5);
  float where = exp(-pow((a + 0.52) / 0.27, 2.0)) + 0.7 * exp(-pow((a - 0.56) / 0.2, 2.0)) + 0.05;
  float m = 1250.0 * noise(p / 4300.0 + 5.0) + 380.0 * noise(p / 1500.0 + 2.0) + 110.0 * noise(p / 520.0 + 9.0) + 30.0 * noise(p / 170.0) - 420.0;
  return h + smoothstep(3000.0, 7000.0, r) * where * max(m, 0.0) * (1.0 - 0.5 * exp(-max(m, 0.0) / 80.0));
}

vec4 ground(vec2 p, float texel) {
  float e = max(0.2, 0.004 * length(p)), h = rolling(p), light = 0.0;
  vec2 g = vec2(rolling(p + vec2(e, 0.0)) - rolling(p - vec2(e, 0.0)), rolling(p + vec2(0.0, e)) - rolling(p - vec2(0.0, e))) / (2.0 * e);
  vec3 l = lumps(p, texel, 0.0);
  h += l.x;
  g += l.yz;
  float cell = 1100.0;
  for (int k = 0; k < 22; k++) {
    if (cell * 0.45 < 2.0 * texel) break; // even its largest crater is smaller than the map can hold here
    vec2 q = p / cell + float(k) * 7.31, id = floor(q);
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
      vec2 c = id + vec2(float(i), float(j)), rnd = hash2(c + float(k) * 13.1);
      if (rnd.x > 0.34) continue;
      float rad = 0.12 + 0.33 * rnd.y * rnd.y, age = pow(hash(c + 91.7), 0.45);
      vec2 ctr = c + hash2(c + 3.3), d = q - ctr;
      float rho = length(d) / rad;
      if (rho > 2.2) continue;
      float size = rad * cell;
      vec2 at = (ctr - float(k) * 7.31) * cell; // where it is in the world
      float w = smoothstep(2.0, 4.5, size / texel)                         // fades out as it gets too small to store
              * smoothstep(1.0, 0.6, size / (0.11 * length(at) + 0.5))     // nothing big near the slab
              * smoothstep(0.0, 0.3, slabDistance(at) - size * 1.25);      // and none under it
      if (w <= 0.0) continue;
      rho *= 1.0 + 0.09 * (noise(vec2(atan(d.y, d.x) * 1.6 + rnd.y * 50.0, rnd.x * 9.0)) - 0.5); // not quite round
      vec2 f = crater(rho, age, max(0.05 + 0.3 * age * age, 2.2 * texel / size)) * (size > 60.0 ? 0.6 : 1.0);
      h += w * f.x * size;
      g += w * f.y * d / max(length(d), 1e-5);
      // fresh ones are brighter inside, and threw bright rays
      float fresh = max(1.0 - age * 2.6, 0.0);
      float rays = 0.5 + 0.5 * noise(vec2(atan(d.y, d.x) * 5.0 + hash(c) * 40.0, rho * 0.7));
      light += w * fresh * (rho < 1.0 ? 0.55 : 0.75 * rays * rays * exp(-(rho - 1.0) * 2.4));
    }
    cell *= 0.6;
  }
  vec2 fromEye = p - uEye.xz;
  float tone = 0.86 + 0.22 * noise(p / 55.0 + 2.0) + 0.14 * noise(p / 9.0) - 0.08 * smoothstep(3200.0, 7500.0, length(p));
  return vec4(h - dot(fromEye, fromEye) / (2.0 * MOON), g, tone + 0.55 * min(light, 1.2));
}
`;

const PICTURE = /* glsl */ `
vec3 stars(vec3 rd) {
  vec3 c = vec3(0.0);
  for (int i = 0; i < 2; i++) {
    float scale = i == 0 ? 260.0 : 95.0, cut = i == 0 ? 0.80 : 0.86;
    vec2 sp = vec2(atan(rd.x, -rd.z) * cos(0.25), asin(rd.y)) * scale;
    vec2 id = floor(sp), f = fract(sp) - 0.2 - 0.6 * hash2(id + 3.0 + float(i) * 37.0);
    float m = hash(id + 11.0 + float(i) * 5.0);
    if (m < cut) continue;
    float b = pow((m - cut) / (1.0 - cut), i == 0 ? 3.0 : 6.0), r = uPix * scale * (0.6 + (i == 0 ? 0.35 : 1.1) * b);
    c += mix(vec3(1.0, 0.84, 0.70), vec3(0.72, 0.84, 1.0), hash(id + 5.0)) * (i == 0 ? 0.02 + 0.22 * b : 0.05 + 1.5 * b) * exp(-dot(f, f) / (r * r));
  }
  // the galaxy's band, faint, rising to the left
  float band = dot(rd, normalize(vec3(0.52, 0.80, 0.30)));
  float milk = exp(-band * band * 26.0) * (0.35 + 0.65 * fbm(rd.xy * 5.0 + 3.0)) * smoothstep(0.38, 0.62, fbm(rd.xy * 2.3 + rd.z));
  return c * (1.0 + 2.5 * milk) + vec3(0.72, 0.78, 1.0) * milk * 0.012;
}

float sphereNoise(vec3 p) { return tnoise(p) * 0.5 + tnoise(p * 2.02 + 3.1) * 0.25 + tnoise(p * 4.1 + 7.7) * 0.125 + tnoise(p * 8.3 + 1.3) * 0.0625 + tnoise(p * 16.9) * 0.03; }

// The Earth: half lit by the same sun, oceans, land, ice and weather under a thin skin of air.
vec3 earth(vec3 rd) {
  vec3 e = normalize(EARTH), sun = normalize(SUN);
  const float R = 0.058;
  float ang = acos(clamp(dot(rd, e), -1.0, 1.0));
  if (ang > R * 1.5) return vec3(0.0);
  vec3 ux = normalize(cross(vec3(0.0, 1.0, 0.0), e)), uy = cross(e, ux);
  vec2 d = vec2(dot(rd, ux), dot(rd, uy)) / sin(R);
  float r2 = dot(d, d), r = sqrt(r2);
  // the air seen edge-on, past the limb
  vec3 nl = normalize(d.x * ux + d.y * uy);
  vec3 rimAir = vec3(0.20, 0.45, 1.0) * 0.8 * smoothstep(-0.25, 0.35, dot(nl, sun));
  if (r2 >= 1.0) return rimAir * exp(-(r - 1.0) / 0.012);
  vec3 c;
  vec3 n = normalize(d.x * ux + d.y * uy - sqrt(1.0 - r2) * e);
  // turn the globe: its axis tipped, a good hemisphere toward us
  vec3 m = n;
  m.xy = mat2(0.92, -0.39, 0.39, 0.92) * m.xy;
  m.xz = mat2(0.36, 0.933, -0.933, 0.36) * m.xz;
  float lat = m.y;
  vec3 w = m * 1.9 + 0.35 * vec3(tnoise(m * 2.3 + 4.0), tnoise(m * 2.3 + 9.0), tnoise(m * 2.3 + 1.0));
  float land = sphereNoise(w + vec3(2.7, 0.3, 5.1)) - 0.50 - 0.10 * smoothstep(0.75, 1.0, abs(lat));
  vec3 sea = mix(vec3(0.006, 0.035, 0.15), vec3(0.02, 0.12, 0.25), smoothstep(-0.06, 0.0, land));
  float dry = sphereNoise(w * 1.7 + 11.0);
  vec3 soil = mix(vec3(0.025, 0.07, 0.022), vec3(0.20, 0.13, 0.07), smoothstep(0.5, 0.66, dry + 0.2 * (1.0 - abs(lat) * 2.0)));
  vec3 surf = mix(sea, soil, smoothstep(0.0, 0.012, land));
  surf = mix(surf, vec3(0.80, 0.84, 0.88), smoothstep(0.80, 0.90, abs(lat) + 0.08 * dry)); // ice at the poles
  // weather: bands along the latitudes, curled by storms
  vec3 cw = m * vec3(2.2, 5.0, 2.2);
  cw += 0.9 * vec3(tnoise(m * 3.1 + 2.0), tnoise(m * 3.1 + 5.0), tnoise(m * 3.1 + 8.0)) + 0.25 * vec3(tnoise(m * 9.0), tnoise(m * 9.0 + 3.0), tnoise(m * 9.0 + 6.0));
  float cloud = smoothstep(0.50, 0.70, sphereNoise(cw * 1.3 + 3.0) + 0.08 * abs(lat));
  surf = mix(surf, vec3(0.80, 0.83, 0.87), cloud * 0.92);
  float day = dot(n, sun), lit = smoothstep(-0.10, 0.22, day);
  float glint = pow(max(dot(reflect(-sun, n), -e), 0.0), 60.0) * (1.0 - cloud) * step(land, 0.0);
  c = surf * lit * (0.6 + 0.6 * max(day, 0.0)) * 1.15 + vec3(1.0, 0.9, 0.7) * glint * 0.8 * lit;
  // air: blue over everything toward the limb, a red line along the terminator
  float rim = pow(1.0 - sqrt(1.0 - r2), 2.5);
  c = mix(c, vec3(0.30, 0.55, 1.0) * 0.9 * lit, 0.08 + 0.6 * rim) + vec3(0.1, 0.25, 0.6) * 0.03 * pow(rim, 3.0);
  c += vec3(1.0, 0.35, 0.12) * 0.10 * smoothstep(0.16, 0.0, abs(day - 0.02)) * (0.4 + 0.6 * cloud);
  return mix(rimAir, c, smoothstep(1.0, 1.0 - 3.0 * uPix / sin(R), r));
}

vec3 sky(vec3 rd) {
  vec3 e = earth(rd);
  return stars(rd) * (1.0 - smoothstep(0.0, 0.02, dot(e, vec3(1.0)))) * smoothstep(0.9975, 0.992, dot(rd, normalize(EARTH))) + e;
}

const float ROCK = 0.9, PEBBLE = 0.22;
// Rocks: one to a cell of the ground, where there is one: a block cut by seven planes, sunk a little into the dust.
// Two sizes of cell: boulders and stones (0.9 m), and pebbles (0.22 m) near the camera.
bool rockIn(vec2 cell, float grid, out vec3 ctr, out float size) {
  vec2 r = hash2(cell + 17.0 + grid);
  bool big = grid > 0.5;
  float field = smoothstep(0.55, 0.85, noise(cell * grid * 0.1 + 5.0) * 0.7 + noise(cell * grid * 0.34) * 0.3);
  if (r.x > (big ? 0.035 + 0.30 * field : 0.10 + 0.5 * field)) return false;
  size = big ? 0.025 + 0.24 * pow(r.y, 5.0) : 0.006 + 0.022 * r.y * r.y;
  vec2 xz = (cell + 0.5 + (hash2(cell + 3.0) - 0.5) * (1.0 - 2.3 * size / grid)) * grid;
  if (slabDistance(xz) < size * 1.5 + 0.1) return false;
  ctr = vec3(xz.x, groundAt(xz).x - size * 0.2, xz.y);
  return true;
}
bool rockHit(vec3 o, vec3 d, vec3 ctr, float size, vec2 cell, out float t, out vec3 n) {
  o -= ctr;
  float t0 = 0.0, t1 = 1e9;
  n = vec3(0.0, 1.0, 0.0);
  for (int i = 0; i < 7; i++) {
    vec2 h = hash2(cell + float(i) * 5.7 + 1.3);
    float az = (float(i) + h.x) * 1.0472;
    vec3 pn = i == 6 ? normalize(vec3(h.x - 0.5, 1.8, h.y - 0.5)) : normalize(vec3(cos(az), h.y * 0.9 + 0.1, sin(az)));
    float dn = dot(pn, d), on = dot(pn, o) - size * (i == 6 ? 0.55 : 0.6) * (0.7 + 0.3 * hash(cell + float(i) * 9.1));
    if (dn < 0.0) { float tt = -on / dn; if (tt > t0) { t0 = tt; n = pn; } }
    else if (dn > 0.0) t1 = min(t1, -on / dn);
    else if (on > 0.0) return false;
    if (t0 > t1) return false;
  }
  t = t0;
  return t0 > 0.0;
}
// Walks the cells under a ray between two distances; the nearest rock it meets, if any.
bool rocks(vec3 ro, vec3 rd, float grid, float from, float to, inout float t, inout vec3 n, inout vec2 which) {
  vec2 o = (ro.xz + rd.xz * from) / grid, d = rd.xz / grid, cell = floor(o), stp = sign(d);
  vec2 side = (cell + max(stp, 0.0) - o) / d, delta = abs(1.0 / d);
  bool any = false;
  for (int i = 0; i < 26; i++) {
    vec3 ctr; float size, th; vec3 nh;
    if (rockIn(cell, grid, ctr, size) && rockHit(ro, rd, ctr, size, cell, th, nh) && th < t) { t = th; n = nh; which = cell + grid; any = true; }
    float next = min(side.x, side.y);
    if (from + next > to || any) break;
    if (side.x < side.y) { side.x += delta.x; cell.x += stp.x; } else { side.y += delta.y; cell.y += stp.y; }
  }
  return any;
}

// Sunlight at a point: past the terrain, the monolith and the rocks.
float sunAt(vec3 p, float near, float foot) {
  vec3 sun = normalize(SUN);
  float lit = slabShadow(p, sun, 110.0);
  if (lit <= 0.0) return 0.0;
  lit *= groundShadow(p, sun, max(0.02, foot * 1.5), 900.0, 140.0);
  if (lit <= 0.0 || near > 130.0) return lit;
  float t = 1e9; vec3 n; vec2 which;
  if (rocks(p + sun * 0.002, sun, ROCK, 0.0, 3.2, t, n, which)) return 0.0;
  if (near < 34.0 && rocks(p + sun * 0.001, sun, PEBBLE, 0.0, 0.35, t, n, which)) return 0.0;
  return lit;
}

vec3 groundLight(vec3 p, vec3 n, vec3 view, float near, float foot, float tone) {
  vec3 sun = normalize(SUN);
  float lit = sunAt(p, near, foot);
  vec3 c = DUST * tone * SUNLIGHT * dust(dot(n, sun), dot(n, view), dot(sun, view)) * lit;
  // what the shadows get: light off the sunlit ground around, and a little from the Earth
  c += DUST * tone * (SUNLIGHT * 0.010 * (0.5 + 0.5 * n.y) + vec3(0.2, 0.4, 1.0) * 0.004 * max(dot(n, normalize(EARTH)), 0.0));
  return c;
}

// The plain as the monolith's face mirrors it. What it faces lies beside and behind the camera, where the height
// map doesn't reach, so apart from the ground at its own foot it is shown a copy of the mapped ground turned a
// quarter of the way round (with the sun turned the same way): one stretch of moon looks much like another.
vec3 mirrored(vec3 p, vec3 r) {
  vec3 sun = normalize(SUN);
  if (r.y > -0.003) {
    // the horizon behind the camera: a low bright line of far ground under the black
    float rise = 0.010 + 0.012 * noise(vec2(atan(r.x, r.z) * 9.0, 3.0));
    return r.y > rise ? vec3(0.0) : DUST * SUNLIGHT * dust(sun.y, 0.05, dot(sun, -r)) * smoothstep(rise, rise - 0.004, r.y);
  }
  float t = -p.y / r.y;
  vec3 q = p + r * t;
  float lit = slabShadow(q, sun, 110.0);
  vec2 uv = groundUV(q.xz);
  if (smoothstep(1.0, 0.9, abs(uv.x * 2.0 - 1.0)) * smoothstep(0.0, 0.04, uv.y) < gRand) {
    const mat2 turn = mat2(0.1045, -0.9945, 0.9945, 0.1045);
    q.xz = uEye.xz + turn * (q.xz - uEye.xz);
    sun.xz = turn * sun.xz;
    r.xz = turn * r.xz;
  }
  vec4 g = groundAt(q.xz);
  float fade = exp(-t / 400.0); // far off, the mirror only holds the tone
  vec3 n = normalize(vec3(-g.y * fade, 1.0, -g.z * fade));
  lit *= mix(1.0, groundShadow(vec3(q.x, g.x + 0.01, q.z), sun, 0.05 + t * 0.004, 300.0, 40.0), fade);
  return DUST * mix(1.0, g.w, fade) * SUNLIGHT * (dust(dot(n, sun), dot(n, -r), dot(sun, -r)) * lit + 0.010);
}

// The monolith: black and polished. Its face is turned from the sun and holds a dark mirror of the plain; its
// narrow side takes the sun full on; the edges between catch it as a line.
vec3 monolith(vec3 rd, vec3 n, vec3 lp) {
  vec3 sun = normalize(SUN), p = toWorld(lp + vec3(0.0, uSlab.y * 0.5, 0.0));
  float fres = 0.07 + 0.93 * pow(1.0 - abs(dot(rd, n)), 5.0);
  vec3 c = mirrored(p, reflect(rd, n)) * fres;
  float facing = max(dot(n, sun), 0.0);
  float shade = facing > 0.0 ? groundShadow(p, sun, 0.3, 500.0, 60.0) : 0.0;
  c += vec3(0.060, 0.058, 0.056) * SUNLIGHT * facing * shade;                                         // satin black in full sun
  c += SUNLIGHT * 5.0 * pow(max(dot(reflect(rd, n), sun), 0.0), 50.0) * shade;                         // the sun itself, on the edges
  c += vec3(0.020, 0.020, 0.021) * (DUST * SUNLIGHT * 0.5 * (0.5 - 0.5 * n.y) + vec3(0.2, 0.4, 1.0) * 0.02); // the ground's light, and the Earth's
  return c;
}

vec3 picture(vec3 ro, vec3 rd) {
  float ts; vec3 ns, lp;
  bool onSlab = slabHit(ro, rd, ts, ns, lp);
  float tg = groundHit(rd, false);
  vec3 c;
  // rocks: looked for from where the ray comes within their height of the ground, and again just before it lands
  float tr = tg > 0.0 ? tg : 1e9, tl = groundHit(rd, true);
  vec3 nr; vec2 which;
  bool onRock = false;
  if (tl > 0.0 && tl < 130.0) {
    float cells = 1.0 / max(length(rd.xz), 0.05);
    onRock = rocks(ro, rd, ROCK, tl, tr, tr, nr, which);
    if (!onRock && tg > 0.0 && tg - tl > 26.0 * ROCK * cells) onRock = rocks(ro, rd, ROCK, tg - 14.0 * ROCK * cells, tg, tr, nr, which);
    if (tg > 0.0 && tg < 34.0 && rocks(ro, rd, PEBBLE, max(tg - 22.0 * PEBBLE * cells, 0.0), tg, tr, nr, which)) onRock = true;
  }
  if (onSlab && ts < tr) c = monolith(rd, ns, lp);
  else if (onRock) {
    vec3 p = ro + rd * tr;
    float foot = uPix * tr;
    nr = normalize(nr + 0.35 * vec3(noise(p.xz * 60.0) - 0.5, 0.0, noise(p.zx * 60.0 + 7.0) - 0.5) * smoothstep(3.0, 1.0, foot * 60.0));
    float tone = 1.35 + 0.9 * hash(which + 4.0) - 0.5 * noise(p.xy * 25.0 + which);
    c = groundLight(p + nr * 0.003, nr, -rd, tr, foot, tone);
  } else if (tg > 0.0) {
    vec3 p = ro + rd * tg;
    vec4 g = groundAt(p.xz);
    float foot = uPix * tg / sqrt(max(-rd.y, 0.04));
    vec2 fine = lumps(p.xz, groundTexel(p.xz), foot).yz;
    vec3 n = normalize(vec3(-g.y - fine.x, 1.0, -g.z - fine.y));
    float speck = (noise(p.xz * 37.0) - 0.5) * smoothstep(1.0, 3.0, 0.027 / foot) + (noise(p.xz * 9.0 + 5.0) - 0.5) * smoothstep(1.0, 3.0, 0.11 / foot);
    c = groundLight(vec3(p.x, g.x + 0.004, p.z), n, -rd, tg, uPix * tg, g.w * (1.0 + 0.2 * speck));
  } else c = sky(rd);
  vec2 v = rd.xy - vec2(0.0, 0.1);
  c *= (1.0 - 0.5 * dot(v, v)) * mix(0.5, 1.0, smoothstep(-0.52, -0.12, rd.y)); // the lens lets the corners fall off, and the exposure is held back toward the foreground, where the words go
  return screen(c);
}
`;

export const content: Content = {
  brand: "Luna",
  title: "Luna — Your Models Run Where Nothing Else Does",
  description:
    "Luna is private compute for teams that train large models. Reserve capacity in minutes, run without neighbours, and pay only while the lights are on.",
  vars: { "--steel": "#a9aebb", "--sky-tint": "rgba(0, 0, 0, 0.4)" },
  nav: { links: ["Platform", "Capacity", "Regions", "Pricing", "Docs"], heroActive: "Platform", readyActive: "Capacity", account: "Account", cta: "Get Access" },
  hero: {
    badge: "Highest-rated private compute, two years running",
    lines: ["Your Models Run", "Where Nothing Else Does"],
    lead: "Luna is private compute for teams that train large models. Reserve capacity in minutes, run without neighbours, and pay only while the lights are on.",
    primary: "See Capacity",
    secondary: "Read Docs",
  },
  ready: {
    first: "Capacity Reserved",
    second: "Before You Deploy",
    more: "More",
    text: "Request access remotely, receive your keys instantly, and start with storage, networking and monitoring already set up.",
    cta: "Request access",
    scroll: "Scroll down for more ↓",
  },
  card: { name: "SEAN GALT", number: "9276 9400 2812 0000" },
  art: {
    scene: {
      camera: { eye: [0, 2.02, 7.4], pitch: 0.043, vfov: 61 },
      slab: { w: 2.23, h: 3.5, t: 0.3, turn: (22 * Math.PI) / 180, radius: 0.04, bevel: 0.008 },
      samples: [8, 3],
      common: COMMON,
      ground: { glsl: GROUND, far: 14000, lift: 0.5 },
      picture: PICTURE,
    },
    product: { from: "#0a0b0e", mid: "#22242b", to: "#4d515c", ink: "#f1f2f4", chip: ["#e2e4e9", "#8d919b"], line: "ACCESS KEY  ·  9276 9400 2812" },
  },
};
