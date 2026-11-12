import { useEffect, useRef, useState } from "react";
import styles from "./Cursor.module.css";

const FOLLOW = 0.3; // share of the remaining distance covered per frame at 60 fps
const FRAME = 1000 / 60;

/** A glass disc that eases after the pointer, on devices with a mouse. */
export function Cursor() {
  const [fine] = useState(() => window.matchMedia("(hover: hover) and (pointer: fine)").matches);
  const disc = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = disc.current;
    if (!fine || !el) return;
    const at = { x: innerWidth / 2, y: innerHeight / 2 };
    const to = { ...at };
    let then = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      frame = requestAnimationFrame(tick);
      const k = 1 - (1 - FOLLOW) ** ((now - then) / FRAME);
      then = now;
      at.x += (to.x - at.x) * k;
      at.y += (to.y - at.y) * k;
      el.style.transform = `translate3d(${at.x}px, ${at.y}px, 0)`;
    };
    frame = requestAnimationFrame(tick);
    const move = (e: PointerEvent) => {
      to.x = e.clientX;
      to.y = e.clientY;
      el.style.opacity = "1";
    };
    const out = (e: MouseEvent) => {
      if (!e.relatedTarget) el.style.opacity = "0";
    };
    window.addEventListener("pointermove", move);
    document.addEventListener("mouseout", out);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", move);
      document.removeEventListener("mouseout", out);
    };
  }, [fine]);

  return fine ? <div ref={disc} className={styles.cursor} aria-hidden="true" /> : null;
}
