// The picture behind the hero, rendered once in code in place of a photo: a place with a slab standing in it,
// ray-traced by fragment shaders into a canvas and handed to the page as an image. The camera is fixed, so the
// slab's four corners in the picture are known, and the page maps the card's light and the portal onto them.
//
// A scene is drawn in up to three steps, each in tiles so the page stays alive and the counter shows real progress:
//   1. `dome`    (optional) the sky, into a panorama the picture can look up in any direction, sharp or blurred
//                (what water and glass reflect);
//   2. `ground`  (optional) the terrain, into a height map laid out around the camera (azimuth across, distance on a
//                log scale up), then swept so that every ray from the eye finds the first thing it meets in a
//                handful of lookups, however much terrain there is;
//   3. `picture` the image itself, several rays per pixel.

/** The picture's size in image pixels: corners, and the layout in Portal.module.css, are in this space. */
export const IMAGE = { w: 4096, h: 2640 };

export type SceneSpec = {
  camera: { eye: [number, number, number]; pitch: number; vfov: number }; // pitch in radians, vfov in degrees
  /** Stands on y = 0 at the origin, turned about y. `radius` rounds its outline, `bevel` its edges. */
  slab: { w: number; h: number; t: number; turn: number; radius: number; bevel: number };
  /** Rays per pixel: on a desktop, on a touch device. */
  samples: [number, number];
  /** GLSL every step starts with: the constants and functions they share. */
  common: string;
  /** GLSL `vec4 dome(vec3 rd)`: what the sky adds in that direction (premultiplied, alpha = how much it hides). */
  dome?: string;
  /** GLSL `vec4 ground(vec2 xz, float texel)`: the height there, its slope along x and along z, and one value of the
      scene's own; `texel` is the size of the map's cell there, in metres (smaller detail can't be stored). The map
      runs from 3 m out to `far`; `lift` is the tallest thing that stands on the ground (see groundHit). */
  ground?: { glsl: string; far: number; lift: number };
  /** GLSL `vec3 picture(vec3 ro, vec3 rd)`: the colour one ray sees, ready for the screen. */
  picture: string;
};

const PRELUDE = /* glsl */ `#version 300 es
precision highp float;
precision highp sampler2D;
out vec4 o;
uniform vec2 R;       // this step's target, in pixels
uniform vec3 uEye, uSlab;
uniform float uPitch, uTan, uTurn, uRadius, uBevel;
uniform float uPix;   // the angle one pixel of the picture covers, in radians
uniform float uFine;  // 1 on a desktop, lower on a touch device: scenes scale their step counts by it
uniform int uSamples;
uniform sampler2D uNoise;
float gRand = 0.5;    // a different random number for every ray
float gSeq = 0.5;     // and one that steps evenly through 0..1 over a pixel's rays, starting somewhere else in each pixel

const float PI = 3.14159265;
float hash(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
vec2 hash2(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973)); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.xx + p3.yz) * p3.zy); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p), u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
// Value noise with its gradient: (value, d/dx, d/dy).
vec3 noised(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0), du = 30.0 * f * f * (f * (f - 2.0) + 1.0);
  float a = hash(i), b = hash(i + vec2(1, 0)), c = hash(i + vec2(0, 1)), d = hash(i + vec2(1, 1));
  return vec3(a + (b - a) * u.x + (c - a) * u.y + (a - b - c + d) * u.x * u.y, du * (vec2(b - a, c - a) + (a - b - c + d) * u.yx));
}
float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { s += a * noise(p); p = mat2(1.6, 1.2, -1.2, 1.6) * p + 11.7; a *= 0.5; } return s; }
// Smooth 3D noise out of a small texture: cheap enough to march clouds through.
float tnoise(vec3 x) {
  vec3 p = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
  vec2 rg = textureLod(uNoise, (p.xy + vec2(37.0, 239.0) * p.z + f.xy + 0.5) / 256.0, 0.0).yx;
  return mix(rg.x, rg.y, f.z);
}
// Film response, then the screen's curve.
vec3 screen(vec3 x) { x = max(x, 0.0); return pow(clamp(x * (2.51 * x + 0.03) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0), vec3(1.0 / 2.2)); }

// The slab: a thin block with a rounded outline and softened edges, standing on y = 0 at the origin, turned about
// the vertical. "Local" is its own space: x across, y up from its centre, z through it.
vec3 toLocal(vec3 v) { float c = cos(uTurn), s = sin(uTurn); return vec3(c * v.x - s * v.z, v.y, s * v.x + c * v.z); }
vec3 toWorld(vec3 v) { float c = cos(uTurn), s = sin(uTurn); return vec3(c * v.x + s * v.z, v.y, -s * v.x + c * v.z); }
vec3 slabLocal(vec3 p) { return toLocal(p) - vec3(0.0, uSlab.y * 0.5, 0.0); }
// Distance to the slab's outline in its own plane (negative inside).
float slabEdge(vec3 lp) {
  vec2 d = abs(lp.xy) - (uSlab.xy * 0.5 - uRadius);
  return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - uRadius;
}
float sdSlab(vec3 lp) {
  vec2 w = vec2(slabEdge(lp), abs(lp.z) - uSlab.z * 0.5) + uBevel;
  return min(max(w.x, w.y), 0.0) + length(max(w, 0.0)) - uBevel;
}
vec3 slabNormal(vec3 lp) {
  vec2 e = vec2(4e-4, 0.0);
  return normalize(vec3(sdSlab(lp + e.xyy) - sdSlab(lp - e.xyy), sdSlab(lp + e.yxy) - sdSlab(lp - e.yxy), sdSlab(lp + e.yyx) - sdSlab(lp - e.yyx)));
}
// Where a ray meets the slab: the distance, the surface normal (world) and the point (local).
bool slabHit(vec3 ro, vec3 rd, out float t, out vec3 n, out vec3 lp) {
  vec3 hs = uSlab * 0.5, o = slabLocal(ro), d = toLocal(rd);
  vec3 inv = 1.0 / d, t0 = (-hs - o) * inv, t1 = (hs - o) * inv, a = min(t0, t1), b = max(t0, t1);
  float tn = max(max(a.x, a.y), a.z), tf = min(min(b.x, b.y), b.z);
  if (tn > tf || tf < 0.0) return false;
  t = max(tn, 0.0);
  for (int i = 0; i < 40; i++) {
    float s = sdSlab(o + d * t);
    if (s < 2e-4) break;
    t += s;
    if (t > tf) return false;
  }
  lp = o + d * t;
  n = toWorld(slabNormal(lp));
  return true;
}
// How much of a light in direction l reaches p past the slab: 0 in its shadow, 1 clear of it. k sharpens the edge
// (1 / the light's angular radius).
float slabShadow(vec3 p, vec3 l, float k) {
  vec3 hs = uSlab * 0.5 + 0.6, o = slabLocal(p), d = toLocal(l);
  vec3 inv = 1.0 / d, t0 = (-hs - o) * inv, t1 = (hs - o) * inv, a = min(t0, t1), b = max(t0, t1);
  float tn = max(max(a.x, a.y), a.z), tf = min(min(b.x, b.y), b.z);
  if (tn > tf || tf < 0.0) return 1.0;
  float t = max(tn, 0.02), res = 1.0;
  for (int i = 0; i < 48; i++) {
    float s = sdSlab(o + d * t);
    res = min(res, k * s / t);
    if (res < 0.001 || t > tf) break;
    t += max(s, 0.004);
  }
  return smoothstep(0.0, 1.0, res);
}
vec3 rayDir(vec2 frag, vec2 size) {
  vec2 uv = (frag - 0.5 * size) / (0.5 * size.y);
  vec3 rd = normalize(vec3(uv * uTan, -1.0));
  float c = cos(uPitch), s = sin(uPitch);
  return vec3(rd.x, c * rd.y - s * rd.z, s * rd.y + c * rd.z);
}
`;

// The panorama: azimuth ±DOME_AZ around straight ahead across, elevation DOME_LO..DOME_HI up (radians).
const DOME = /* glsl */ `
const float DOME_AZ = 1.25, DOME_LO = -0.02, DOME_HI = 0.66;
vec3 domeDir(vec2 uv) {
  float a = (uv.x * 2.0 - 1.0) * DOME_AZ, e = mix(DOME_LO, DOME_HI, uv.y);
  return vec3(sin(a) * cos(e), sin(e), -cos(a) * cos(e));
}
`;
const DOME_READ = /* glsl */ `
uniform sampler2D uDome;
uniform vec2 uDomeSize;
// The sky's panorama in a direction, blurred over an angle (radians). Fades out where the panorama ends.
vec4 pano(vec3 rd, float blur) {
  vec2 uv = vec2(atan(rd.x, -rd.z) / DOME_AZ * 0.5 + 0.5, (asin(clamp(rd.y, -1.0, 1.0)) - DOME_LO) / (DOME_HI - DOME_LO));
  float edge = smoothstep(1.0, 0.9, abs(uv.x * 2.0 - 1.0)) * smoothstep(1.0, 0.88, uv.y);
  return textureLod(uDome, clamp(uv, 0.0, 1.0), log2(max(blur * uDomeSize.x / (2.0 * DOME_AZ), 1.0))) * edge;
}
`;

// The height map: azimuth ±GROUND_AZ around straight ahead across, distance from the eye GROUND_NEAR..far up, on a
// log scale, so a cell is about as big as the pixels that look at it wherever it is.
const GROUND = /* glsl */ `
const float GROUND_AZ = 0.98, GROUND_NEAR = 3.0;
uniform float uGroundFar, uLift;
uniform vec2 uGroundSize;
// The size of the map's cell at a place, in metres (its longer side).
float groundTexel(vec2 xz) { return length(xz - uEye.xz) * max(2.0 * GROUND_AZ / uGroundSize.x, log(uGroundFar / GROUND_NEAR) / uGroundSize.y); }
vec2 groundXZ(vec2 uv) {
  float a = (uv.x * 2.0 - 1.0) * GROUND_AZ, r = GROUND_NEAR * pow(uGroundFar / GROUND_NEAR, uv.y);
  return uEye.xz + r * vec2(sin(a), -cos(a));
}
vec2 groundUV(vec2 xz) {
  vec2 d = xz - uEye.xz;
  return vec2(atan(d.x, -d.y) / GROUND_AZ * 0.5 + 0.5, log(max(length(d), 1e-3) / GROUND_NEAR) / log(uGroundFar / GROUND_NEAR));
}
`;
const GROUND_DRAW = /* glsl */ `
void main() {
  vec2 xz = groundXZ(gl_FragCoord.xy / R);
  o = ground(xz, groundTexel(xz));
}`;
// The sweep: for every cell, the highest line of sight from the eye over everything nearer in its column, kept as
// the height that line has at the cell (x: over the ground itself, y: over the ground raised by uLift). Each pass
// looks twice as far back as the last, so twelve passes cover four thousand rows.
const GROUND_SWEEP = /* glsl */ `
uniform sampler2D uHeight, uSelf;
uniform int uPass;
vec2 reach(ivec2 px) { return uPass == 0 ? texelFetch(uHeight, px, 0).xx + vec2(0.0, uLift) : texelFetch(uSelf, px, 0).xy; }
void main() {
  ivec2 px = ivec2(gl_FragCoord.xy);
  int back = 1 << uPass;
  vec2 a = reach(px);
  if (px.y >= back) a = max(a, uEye.y + (reach(px - ivec2(0, back)) - uEye.y) * exp(log(uGroundFar / GROUND_NEAR) / R.y * float(back)));
  o = vec4(a, 0.0, 1.0);
}`;
const GROUND_READ = /* glsl */ `
uniform sampler2D uHeight, uReach;
// The ground at a place: height, slope along x, slope along z, the scene's own value.
vec4 groundAt(vec2 xz) { return textureLod(uHeight, groundUV(xz), 0.0); }
// How far along a ray from the eye the ground is, or -1 for the sky. With lifted = true: where the ray first comes
// within uLift of the ground (so things standing on it can be looked for from there on).
float groundHit(vec3 rd, bool lifted) {
  float run = length(rd.xz), rise = rd.y / run, u = atan(rd.x, -rd.z) / GROUND_AZ * 0.5 + 0.5, span = log(uGroundFar / GROUND_NEAR);
  float lo = 0.0, hi = 1.0 - 0.5 / uGroundSize.y;
  vec2 last = textureLod(uReach, vec2(u, hi), 0.0).xy;
  if (((lifted ? last.y : last.x) - uEye.y) / (GROUND_NEAR * exp(span * hi)) < rise) return -1.0;
  for (int i = 0; i < 15; i++) {
    float mid = 0.5 * (lo + hi);
    vec2 m = textureLod(uReach, vec2(u, mid), 0.0).xy;
    if (((lifted ? m.y : m.x) - uEye.y) / (GROUND_NEAR * exp(span * mid)) < rise) lo = mid; else hi = mid;
  }
  return GROUND_NEAR * exp(span * hi) / run;
}
// How much of a light in direction l reaches p over the terrain (0..1). k sharpens the shadow's edge (1 / the
// light's angular radius). Steps start at s0 and grow with the distance; for a sharp light they grow slowly at
// first, so that small things nearby throw clean shadows.
float groundShadow(vec3 p, vec3 l, float s0, float far, float k) {
  float res = 1.0, s = s0 * (0.7 + 0.6 * gRand);
  for (int i = 0; i < 110; i++) {
    vec3 q = p + l * s;
    res = min(res, k * (q.y - groundAt(q.xz).x) / s);
    if (res < 0.0 || s > far) break;
    s *= 1.0 + (k > 10.0 && s < 40.0 * s0 ? 0.07 : 0.19) / uFine;
  }
  return smoothstep(0.0, 1.0, res);
}
`;

const DOME_DRAW = /* glsl */ `
void main() { o = dome(domeDir(gl_FragCoord.xy / R)); }`;

// Each ray is a little off the pixel's centre, and their colours are averaged; a light grain on top also keeps the
// long gradients from banding.
const PICTURE_DRAW = /* glsl */ `
void main() {
  vec3 col = vec3(0.0);
  for (int i = 0; i < 16; i++) {
    if (i >= uSamples) break;
    gRand = hash(gl_FragCoord.xy + float(i) * 7.31);
    gSeq = fract(hash(gl_FragCoord.yx + 0.5) + float(i) * 0.61803399);
    col += picture(uEye, rayDir(gl_FragCoord.xy - 0.5 + fract(0.5 + float(i) * vec2(0.7548777, 0.5698403)), R));
  }
  col /= float(uSamples);
  float grain = hash(gl_FragCoord.xy + 3.7) + hash(gl_FragCoord.yx * 1.31 + 9.1) - 1.0;
  o = vec4(col + grain * (1.2 + 3.0 * dot(col, vec3(0.3, 0.6, 0.1)) * (1.0 - dot(col, vec3(0.3, 0.6, 0.1)))) / 255.0, 1.0);
}`;

/** The slab's front corners in image pixels: top left, top right, bottom right, bottom left. */
export function slabCorners({ camera, slab }: SceneSpec): [number, number][] {
  const tan = Math.tan((camera.vfov * Math.PI) / 360);
  const c = Math.cos(slab.turn), s = Math.sin(slab.turn), cp = Math.cos(-camera.pitch), sp = Math.sin(-camera.pitch);
  const hw = slab.w / 2, f = slab.t / 2;
  const corners = [[-hw, slab.h], [hw, slab.h], [hw, 0], [-hw, 0]];
  return corners.map(([x, y]) => {
    const w = [c * x + s * f - camera.eye[0], y - camera.eye[1], -s * x + c * f - camera.eye[2]];
    const v = [w[0], cp * w[1] - sp * w[2], sp * w[1] + cp * w[2]];
    return [IMAGE.w / 2 + (v[0] / -v[2] / tan) * (IMAGE.h / 2), IMAGE.h / 2 - (v[1] / -v[2] / tan) * (IMAGE.h / 2)];
  });
}

// Lets the page breathe between tiles. A message, not a timer: timers are held back in background tabs.
const pause = () =>
  new Promise<void>((resolve) => {
    const channel = new MessageChannel();
    channel.port1.onmessage = () => resolve();
    channel.port2.postMessage(null);
  });

// Sizes of the two maps on a desktop; a touch device gets them at the picture's own reduced scale.
const DOME_SIZE = { w: 4096, h: 1536 };
const GROUND_SIZE = { w: 2048, h: 4096 };
// How the counter is shared between the steps (the picture takes the rest).
const SHARE = { compile: 0.06, dome: 0.3, ground: 0.2 };

/** Renders the scene and returns it as a decoded object URL. `onProgress` gets 0..1 as the tiles finish. */
export async function bakeScene(spec: SceneSpec, onProgress: (p: number) => void): Promise<string> {
  const started = performance.now();
  const touch = window.matchMedia("(pointer: coarse)").matches;
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true, antialias: false, alpha: false, powerPreference: "high-performance" });
  if (!gl) throw new Error("WebGL 2 is not available: the scene can't be drawn");
  const maps = spec.dome || spec.ground;
  if (maps && !gl.getExtension("EXT_color_buffer_float") && !gl.getExtension("EXT_color_buffer_half_float"))
    throw new Error("This device can't draw into float textures: the scene can't be drawn");
  const scale = Math.min(touch ? 0.625 : 1, gl.getParameter(gl.MAX_TEXTURE_SIZE) / IMAGE.w);
  const size = (s: { w: number; h: number }) => ({ w: Math.round(s.w * scale), h: Math.round(s.h * scale) });
  const image = size(IMAGE), domeSize = size(DOME_SIZE), groundSize = size(GROUND_SIZE);
  canvas.width = image.w;
  canvas.height = image.h;

  // Programs: all are handed to the driver at once, and waited for together
  const parallel = gl.getExtension("KHR_parallel_shader_compile");
  const build = (fragment: string) => {
    const program = gl.createProgram()!;
    for (const [type, source] of [[gl.VERTEX_SHADER, "#version 300 es\nin vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }"], [gl.FRAGMENT_SHADER, fragment]] as const) {
      const shader = gl.createShader(type)!;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      gl.attachShader(program, shader);
    }
    gl.bindAttribLocation(program, 0, "p");
    gl.linkProgram(program);
    return program;
  };
  const head = PRELUDE + (spec.dome ? DOME : "") + (spec.ground ? GROUND : "") + spec.common;
  const programs = {
    dome: spec.dome ? build(head + spec.dome + DOME_DRAW) : null,
    ground: spec.ground ? build(head + spec.ground.glsl + GROUND_DRAW) : null,
    sweep: spec.ground ? build(PRELUDE + GROUND + GROUND_SWEEP) : null,
    picture: build(head + (spec.dome ? DOME_READ : "") + (spec.ground ? GROUND_READ : "") + spec.picture + PICTURE_DRAW),
  };
  for (const program of Object.values(programs)) {
    if (!program) continue;
    while (parallel && !gl.getProgramParameter(program, parallel.COMPLETION_STATUS_KHR)) await pause();
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      const log = gl.getAttachedShaders(program)?.map((s) => gl.getShaderInfoLog(s)).join("\n");
      throw new Error(`The scene's shader did not compile: ${gl.getProgramInfoLog(program)}\n${log}`);
    }
  }
  const compiled = performance.now();
  onProgress(SHARE.compile);

  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

  // Textures. Unit 0 is a small noise tile: red is random, green is red moved by (37, 239), which is what lets
  // tnoise() read two layers of 3D noise in one lookup.
  const texture = (unit: number, w: number, h: number, format: "noise" | "float" | "float2", filter: number) => {
    const tex = gl.createTexture()!;
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    if (format === "noise") {
      const data = new Uint8Array(w * h * 4);
      let seed = 20231;
      const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) >>> 24);
      for (let i = 0; i < w * h; i++) { data[i * 4] = random(); data[i * 4 + 2] = random(); data[i * 4 + 3] = random(); }
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) data[(y * w + x) * 4 + 1] = data[(((y - 239 + 2 * h) % h) * w + ((x - 37 + w) % w)) * 4];
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
    } else gl.texStorage2D(gl.TEXTURE_2D, filter === gl.LINEAR_MIPMAP_LINEAR ? Math.floor(Math.log2(Math.max(w, h))) + 1 : 1, format === "float" ? gl.RGBA16F : gl.RG16F, w, h);
    const wrap = format === "noise" ? gl.REPEAT : gl.CLAMP_TO_EDGE;
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, wrap);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, wrap);
    return tex;
  };
  texture(0, 256, 256, "noise", gl.LINEAR);
  const framebuffer = gl.createFramebuffer();
  const target = (tex: WebGLTexture | null) => {
    gl.bindFramebuffer(gl.FRAMEBUFFER, tex ? framebuffer : null);
    if (tex) gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
  };

  const bind = (program: WebGLProgram, w: number, h: number) => {
    gl.useProgram(program);
    const u = (name: string) => gl.getUniformLocation(program, name);
    gl.uniform2f(u("R"), w, h);
    gl.uniform3f(u("uEye"), ...spec.camera.eye);
    gl.uniform1f(u("uPitch"), spec.camera.pitch);
    gl.uniform1f(u("uTan"), Math.tan((spec.camera.vfov * Math.PI) / 360));
    gl.uniform1f(u("uPix"), (2 * Math.tan((spec.camera.vfov * Math.PI) / 360)) / image.h);
    gl.uniform1f(u("uTurn"), spec.slab.turn);
    gl.uniform3f(u("uSlab"), spec.slab.w, spec.slab.h, spec.slab.t);
    gl.uniform1f(u("uRadius"), spec.slab.radius);
    gl.uniform1f(u("uBevel"), spec.slab.bevel);
    gl.uniform1f(u("uFine"), touch ? 0.6 : 1);
    gl.uniform1i(u("uSamples"), spec.samples[touch ? 1 : 0]);
    gl.uniform1i(u("uNoise"), 0);
    gl.uniform1i(u("uDome"), 1);
    gl.uniform2f(u("uDomeSize"), domeSize.w, domeSize.h);
    gl.uniform1i(u("uHeight"), 2);
    gl.uniform1i(u("uReach"), 3);
    gl.uniform2f(u("uGroundSize"), groundSize.w, groundSize.h);
    gl.uniform1f(u("uGroundFar"), spec.ground?.far ?? 1);
    gl.uniform1f(u("uLift"), spec.ground?.lift ?? 0);
    gl.viewport(0, 0, w, h);
    return u;
  };
  // Waits for the GPU to finish what it was given, without holding the page
  const drawn = async () => {
    const sync = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
    gl.flush();
    while (sync && gl.clientWaitSync(sync, 0, 0) === gl.TIMEOUT_EXPIRED) {
      if (gl.isContextLost()) throw new Error("The graphics context was lost while the scene was drawn");
      await pause();
    }
    gl.deleteSync(sync);
  };
  const tiles = async (w: number, h: number, cols: number, rows: number, from: number, to: number) => {
    gl.enable(gl.SCISSOR_TEST);
    for (let i = 0; i < cols * rows; i++) {
      const x = Math.floor(((i % cols) * w) / cols), y = Math.floor((Math.floor(i / cols) * h) / rows);
      gl.scissor(x, y, Math.ceil(w / cols), Math.ceil(h / rows));
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      await drawn();
      onProgress(from + ((to - from) * (i + 1)) / (cols * rows));
    }
    gl.disable(gl.SCISSOR_TEST);
  };

  let at = SHARE.compile;
  if (programs.dome) {
    const dome = texture(1, domeSize.w, domeSize.h, "float", gl.LINEAR_MIPMAP_LINEAR);
    target(dome);
    bind(programs.dome, domeSize.w, domeSize.h);
    await tiles(domeSize.w, domeSize.h, 4, 2, at, (at += SHARE.dome));
    gl.activeTexture(gl.TEXTURE1);
    gl.generateMipmap(gl.TEXTURE_2D);
  }
  const domed = performance.now();
  if (programs.ground && programs.sweep) {
    const height = texture(2, groundSize.w, groundSize.h, "float", gl.LINEAR);
    target(height);
    bind(programs.ground, groundSize.w, groundSize.h);
    await tiles(groundSize.w, groundSize.h, 2, 2, at, (at += SHARE.ground * 0.7));
    // The sweep goes back and forth between two textures; the last one written stays on unit 3
    const pair = [texture(3, groundSize.w, groundSize.h, "float2", gl.LINEAR), texture(4, groundSize.w, groundSize.h, "float2", gl.LINEAR)];
    const u = bind(programs.sweep, groundSize.w, groundSize.h);
    const passes = Math.ceil(Math.log2(groundSize.h));
    for (let i = 0; i < passes; i++) {
      target(pair[i % 2]);
      gl.activeTexture(gl.TEXTURE4);
      gl.bindTexture(gl.TEXTURE_2D, pair[(i + 1) % 2]);
      gl.uniform1i(u("uSelf"), 4);
      gl.uniform1i(u("uPass"), i);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
    gl.activeTexture(gl.TEXTURE3);
    gl.bindTexture(gl.TEXTURE_2D, pair[(passes - 1) % 2]);
    await drawn();
    onProgress((at += SHARE.ground * 0.3));
  }
  const grounded = performance.now();
  target(null);
  bind(programs.picture, image.w, image.h);
  await tiles(image.w, image.h, 4, 6, at, 1);
  const pictured = performance.now();

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.94));
  gl.getExtension("WEBGL_lose_context")?.loseContext();
  if (!blob) throw new Error("The scene could not be encoded");
  const url = URL.createObjectURL(blob);
  const img = new Image();
  img.src = url;
  await img.decode();
  // How long each step took, for anyone looking in the Performance panel
  const steps = { "scene: compile": [started, compiled], "scene: dome": [compiled, domed], "scene: ground": [domed, grounded], "scene: picture": [grounded, pictured], "scene: encode": [pictured, performance.now()], scene: [started, performance.now()] };
  for (const [name, [start, end]] of Object.entries(steps)) performance.measure(name, { start, end });
  return url;
}
