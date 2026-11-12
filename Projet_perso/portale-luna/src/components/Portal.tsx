import { useEffect, useRef, type CSSProperties, type RefObject } from "react";
import { CONTENT } from "../content";
import { lerpQuad, quadToMatrix3d, rectQuad, scaleQuad, segment as seg, type Quad } from "../lib/quad";
import { IMAGE, slabCorners } from "../lib/scene";
import styles from "./Portal.module.css";

/** What Page's GSAP timelines write and Portal reads every frame; all 0 → 1. */
export type PortalState = { scale: number; face: number; flash: number; p: number };

// The card plane, upright, in card pixels
const PLANE_W = 652;
const PLANE_H = 1024;
// Motion, as fractions of the scroll p
const DOLLY = 0.18; // how much the camera moves in
const DOLLY_END = 0.7;
const TURN_END = 0.45; // the slab faces the camera by here
const TURN_HEIGHT = 1.06; // the upright card's height over the slab's average edge height
const GROW = [0.5, 0.82] as const; // the portal grows past the screen
const COVER = 1.2; // how far it overhangs the screen
const LIGHT_OUT = [0.15, 0.4] as const;
const RIM_IN = [0.1, 0.4] as const;
const FILL_IN = [0.35, 0.62] as const;

const CARD_CORNERS: [number, number][] = slabCorners(CONTENT.art.scene);
const CARD_CY = CARD_CORNERS.reduce((a, [, y]) => a + y, 0) / 4 / IMAGE.h; // → --card-cy on the picture box

const CHIP = "https://assets.uberdesigner.ai/portale/card-chip.svg";

const inOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);

export function Portal({ state, scene }: { state: RefObject<PortalState>; scene: string | null }) {
  const media = useRef<HTMLDivElement>(null);
  const over = useRef<HTMLDivElement>(null);
  const photo = useRef<HTMLDivElement>(null);
  const light = useRef<HTMLDivElement>(null);
  const portal = useRef<HTMLDivElement>(null);
  const rim = useRef<HTMLDivElement>(null);
  const fill = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const els = [media.current, over.current, photo.current, light.current, portal.current, rim.current, fill.current];
    if (els.some((el) => !el)) return;
    const [mediaEl, overEl, photoEl, lightEl, portalEl, rimEl, fillEl] = els as HTMLDivElement[];

    let dirty = true;
    const observer = new ResizeObserver(() => (dirty = true));
    observer.observe(mediaEl);
    observer.observe(photoEl);
    let last = "";
    let frame = 0;

    const draw = () => {
      frame = requestAnimationFrame(draw);
      const s = state.current;
      const key = `${s.scale}|${s.face}|${s.flash}|${s.p}`;
      if (!dirty && key === last) return;
      dirty = false;
      last = key;
      const p = s.p;

      // 1. The two layers grow out of the centre of the screen
      mediaEl.style.transform = overEl.style.transform = `scale(${s.scale})`;

      // 2. The slab in the picture
      const W = mediaEl.offsetWidth, H = mediaEl.offsetHeight;
      const bx = photoEl.offsetLeft, by = photoEl.offsetTop, bw = photoEl.offsetWidth, bh = photoEl.offsetHeight;
      const base = CARD_CORNERS.map(([x, y]) => ({ x: bx + (x / IMAGE.w) * bw, y: by + (y / IMAGE.h) * bh })) as Quad;
      const c = { x: base.reduce((a, q) => a + q.x, 0) / 4, y: base.reduce((a, q) => a + q.y, 0) / 4 };

      // 3. The camera moves in
      const d = 1 + DOLLY * inOut(seg(p, 0, DOLLY_END));
      photoEl.style.transformOrigin = `${c.x - bx}px ${c.y - by}px`;
      photoEl.style.transform = `scale(${d})`;
      const inPhoto = scaleQuad(base, c, d);

      // 4. The slab turns to face the camera
      const h = ((inPhoto[3].y - inPhoto[0].y + inPhoto[2].y - inPhoto[1].y) / 2) * TURN_HEIGHT;
      const turned = lerpQuad(inPhoto, rectQuad(c.x, c.y, (h * PLANE_W) / PLANE_H, h), inOut(seg(p, 0, TURN_END)));

      // 5. And grows past the edges of the screen
      const coverH = Math.max(H, (W * PLANE_H) / PLANE_W) * COVER;
      const cover = rectQuad(W / 2, H / 2, (coverH * PLANE_W) / PLANE_H, coverH);
      const quad = lerpQuad(turned, cover, seg(p, GROW[0], GROW[1]) ** 3);

      // 6. Both planes on the same corners
      lightEl.style.transform = portalEl.style.transform = quadToMatrix3d(PLANE_W, PLANE_H, quad);

      // 7. Light out, rim and fill in
      lightEl.style.opacity = String(s.face * (1 - seg(p, ...LIGHT_OUT)));
      rimEl.style.opacity = String(Math.max(s.flash, seg(p, ...RIM_IN)));
      fillEl.style.opacity = String(seg(p, ...FILL_IN));
    };
    frame = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [state]);

  const { name, number } = CONTENT.card;
  return (
    <>
      <div ref={media} className={styles.media} data-portal="media">
        <div ref={photo} className={styles.photo} style={{ "--card-cy": CARD_CY } as CSSProperties}>
          {scene ? <img src={scene} alt="" className={styles.image} /> : null}
        </div>
        <div ref={light} className={`${styles.plane} ${styles.light}`}>
          <div className={styles.face}>
            <span className={`${styles.brand} trim`}>{CONTENT.brand}</span>
            <img src={CHIP} alt="" className={styles.chip} />
            <span className={`${styles.name} trim`}>{name}</span>
            <span className={`${styles.number} trim`}>{number}</span>
          </div>
        </div>
      </div>
      <div ref={over} className={styles.over} data-portal="over">
        <div ref={portal} className={styles.plane}>
          <div ref={fill} className={styles.fill} />
          <div ref={rim} className={styles.rim} />
        </div>
      </div>
    </>
  );
}
