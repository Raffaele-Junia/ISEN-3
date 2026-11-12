import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useEffect, useRef, useState } from "react";
import { CONTENT } from "../content";
import { drawProduct } from "../lib/product";
import { segment as seg } from "../lib/quad";
import { bakeScene } from "../lib/scene";
import { HeroCopy } from "./HeroCopy";
import { Nav, type NavTheme } from "./Nav";
import styles from "./Page.module.css";
import { Portal, type PortalState } from "./Portal";
import { Preloader } from "./Preloader";
import { Ready } from "./Ready";

gsap.registerPlugin(ScrollTrigger);
ScrollTrigger.config({ ignoreMobileResize: true });

// Loading
const COUNTER_FOLLOW = 0.4; // how long the counter takes to catch up with the progress
const COUNTER_CAP = 0.9; // the share of the counter the loading may show
// The intro, in seconds from the moment everything is ready
const T = {
  count: 0, // the counter runs to 100
  countOut: 0.5,
  grow: 0.6, // the picture grows out of the centre
  wordmarkOut: 0.7,
  light: 1.05, // the card's light flickers on, the rim flashes
  badge: 1.1,
  nav: 1.15,
  words: 1.25,
  buttons: 1.55,
  lead: 1.85,
  unlock: 2.3,
};
const WORD_STAGGER = 0.09;
const REDUCED_FADE = 0.4;
// The scroll, in screens, and its moments as fractions of p
const SCROLL_SCREENS = 1.5;
const SCRUB = 0.6;
const COPY_RISE = 120; // design px the hero copy moves up
const COPY_RISE_AT = [0.2, 0.8] as const;
const READY_FADE = [0.79, 0.81] as const;
const DARK_AT = 0.76;
const REVEAL_AT = 0.8;
const HIDE_AT = 0.74;
const REDUCED_READY_FADE = [0.3, 0.6] as const;
// The card on the second screen
const FLOAT = { y: 0.75, turn: 0.75, duration: 3.2 };
const TILT = { y: 8, x: 6, duration: 0.8 };

// The pictures are drawn once per page load, however many times StrictMode runs the effect that asks for them
type Art = { scene: string; product: string };
let loading: Promise<Art | null> | null = null;
let progress = 0;
let report: (p: number) => void = () => {};
function load() {
  loading ??= Promise.all([
    bakeScene(CONTENT.art.scene, (p) => {
      progress = p;
      report(p);
    }),
    drawProduct(CONTENT.art.product, CONTENT.brand),
    ...['300 1em "Geist"', '400 1em "Geist"', '500 1em "Geist"'].map((font) => document.fonts.load(font)),
  ]).then(
    ([scene, product]) => ({ scene, product }),
    (error: unknown) => {
      console.error(error);
      return null;
    },
  );
  return loading;
}

const counterText = (v: number) => `${String(Math.round(v)).padStart(2, "0")}%`;

export function Page() {
  const main = useRef<HTMLElement>(null);
  const state = useRef<PortalState>({ scale: 0, face: 0, flash: 0, p: 0 });
  const counter = useRef({ v: 0 });
  const [art, setArt] = useState<Art | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [theme, setTheme] = useState<NavTheme>("light");
  const [reduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  // The page's setup, and the loading with its counter
  useEffect(() => {
    history.scrollRestoration = "manual";
    window.scrollTo(0, 0);
    const root = document.documentElement;
    root.setAttribute("data-locked", "");
    const click = (e: MouseEvent) => {
      if (e.target instanceof Element && e.target.closest('a[href="#"]')) e.preventDefault();
    };
    document.addEventListener("click", click);

    let alive = true;
    const ctx = gsap.context(() => {
      const el = main.current?.querySelector('[data-preloader-part="counter"]');
      const proxy = counter.current;
      let target = 0;
      const follow = gsap.quickTo(proxy, "v", {
        duration: COUNTER_FOLLOW,
        ease: "power1.out",
        onUpdate: () => {
          if (el) el.textContent = counterText(proxy.v);
        },
      });
      report = (p) => {
        target = Math.max(target, p * COUNTER_CAP * 100);
        follow(target);
      };
      report(progress);
    });
    load().then((result) => {
      if (!alive) return;
      setArt(result);
      setLoaded(true);
    });
    return () => {
      alive = false;
      report = () => {};
      ctx.revert();
      document.removeEventListener("click", click);
      root.removeAttribute("data-locked");
    };
  }, []);

  // The intro, the scroll through the portal and the second screen's reveal
  useEffect(() => {
    const mainEl = main.current;
    const nav = document.querySelector<HTMLElement>("[data-nav]");
    if (!loaded || !mainEl || !nav) return;
    const q = (selector: string) => mainEl.querySelector<HTMLElement>(selector)!;
    const qa = (selector: string) => Array.from(mainEl.querySelectorAll<HTMLElement>(selector));
    const s = state.current;

    const ctx = gsap.context((self) => {
      gsap.killTweensOf(counter.current);
      const counterEl = q('[data-preloader-part="counter"]');
      const hero = q('[data-hero="copy"]');
      const intro = {
        badge: q('[data-intro="badge"]'),
        title: q('[data-intro="title"]'),
        words: qa('[data-intro="title"] [data-word]'),
        buttons: q('[data-intro="buttons"]'),
        lead: q('[data-intro="lead"]'),
      };
      const section = q('[data-ready="section"]');
      const ready = {
        card: q('[data-ready="card"]'),
        float: q('[data-ready="float"]'),
        image: mainEl.querySelector<HTMLElement>('[data-ready="image"]'),
        first: q('[data-ready="first"]'),
        firstWords: qa('[data-ready="first"] [data-word]'),
        second: q('[data-ready="second"]'),
        secondWords: qa('[data-ready="second"] [data-word]'),
        wordmark: q('[data-ready="wordmark"]'),
        more: q('[data-ready="more"]'),
        text: q('[data-ready="text"]'),
        cta: q('[data-ready="cta"]'),
        scroll: q('[data-ready="scroll"]'),
      };
      const unlock = () => {
        document.documentElement.removeAttribute("data-locked");
        ScrollTrigger.refresh();
      };
      const blurIn = (tl: gsap.core.Timeline, el: gsap.TweenTarget, at: number, blur = 10) =>
        tl.fromTo(
          el,
          { opacity: 0, filter: `blur(${blur}px)` },
          { opacity: 1, filter: "blur(0px)", duration: 0.6, ease: "power2.out", clearProps: "filter" },
          at,
        );
      const wordsIn = (tl: gsap.core.Timeline, words: HTMLElement[], at: number) =>
        tl.fromTo(
          words,
          { opacity: 0, filter: "blur(12px)", yPercent: 25 },
          { opacity: 1, filter: "blur(0px)", yPercent: 0, duration: 0.7, ease: "power2.out", stagger: WORD_STAGGER, clearProps: "filter,transform" },
          at,
        );

      // Inline styles the scroll writes outside GSAP, put back on revert
      self.add(() => () => {
        hero.style.transform = "";
        section.style.opacity = "";
        section.style.visibility = "";
        s.p = 0;
      });

      if (reduced) {
        // No counter, no zoom, no portal: everything fades in together, and the second screen cross-fades in
        const tl = gsap.timeline();
        tl.set(s, { scale: 1, face: 1 }, 0);
        tl.fromTo(
          [q('[data-portal="media"]'), nav, intro.badge, intro.title, intro.buttons, intro.lead],
          { opacity: 0 },
          { opacity: 1, duration: REDUCED_FADE, ease: "power1.out" },
          0,
        );
        tl.call(unlock, [], REDUCED_FADE);

        const reveal = gsap.timeline({ paused: true });
        reveal.fromTo(
          [ready.card, ready.first, ready.second, ready.wordmark, ready.more, ready.text, ready.cta, ready.scroll],
          { opacity: 0 },
          { opacity: 1, duration: REDUCED_FADE, ease: "power1.out" },
        );
        let shown = false;
        const proxy = { p: 0 };
        gsap.to(proxy, {
          p: 1,
          ease: "none",
          onUpdate: () => {
            const o = seg(proxy.p, ...REDUCED_READY_FADE);
            section.style.opacity = String(o);
            section.style.visibility = o > 0 ? "visible" : "hidden";
            if (o >= 1 && !shown) {
              shown = true;
              reveal.play();
            } else if (proxy.p < REDUCED_READY_FADE[0] && shown) {
              shown = false;
              reveal.reverse();
            }
            setTheme(o >= 1 ? "dark" : "light");
          },
          scrollTrigger: { trigger: mainEl, start: "top top", end: () => `+=${innerHeight * SCROLL_SCREENS}`, pin: true, scrub: true, invalidateOnRefresh: true },
        });
        return;
      }

      // M1 · The intro
      const tl = gsap.timeline();
      tl.to(counter.current, { v: 100, duration: T.countOut, ease: "power1.out", onUpdate: () => (counterEl.textContent = counterText(counter.current.v)) }, T.count);
      tl.to(counterEl, { opacity: 0, duration: 0.15, ease: "power1.in" }, T.countOut);
      tl.to(s, { scale: 1, duration: 0.85, ease: "power2.out" }, T.grow);
      tl.to(q('[data-preloader-part="wordmark"]'), { opacity: 0, duration: 0.4, ease: "power1.out" }, T.wordmarkOut);
      tl.to(s, { keyframes: { face: [0, 0.8, 0.15, 1, 0.55, 1] }, duration: 0.45, ease: "none" }, T.light);
      tl.to(s, { keyframes: { flash: [0, 1, 0] }, duration: 0.7, ease: "power1.out" }, T.light);
      blurIn(tl, intro.badge, T.badge);
      blurIn(tl, nav, T.nav, 8);
      tl.set(intro.title, { opacity: 1 }, T.words);
      wordsIn(tl, intro.words, T.words);
      blurIn(tl, intro.buttons, T.buttons);
      blurIn(tl, intro.lead, T.lead);
      tl.call(unlock, [], T.unlock);

      // M4 · The second screen's reveal, played and reversed by the scroll
      const reveal = gsap.timeline({ paused: true });
      reveal.fromTo(ready.card, { opacity: 0 }, { opacity: 1, duration: 0.5, ease: "power1.out" }, 0);
      reveal.fromTo(
        ready.float,
        { rotationY: -70, rotation: 18, scale: 0.75, filter: "blur(16px) brightness(1.6)" },
        { rotationY: 0, rotation: 0, scale: 1, filter: "blur(0px) brightness(1)", duration: 1.4, ease: "power3.out", clearProps: "filter" },
        0,
      );
      reveal.set(ready.first, { opacity: 1 }, 0.15);
      wordsIn(reveal, ready.firstWords, 0.15);
      reveal.set(ready.second, { opacity: 1 }, 0.3);
      wordsIn(reveal, ready.secondWords, 0.3);
      reveal.fromTo(ready.wordmark, { opacity: 0 }, { opacity: 1, duration: 1, ease: "power1.out" }, 0.4);
      blurIn(reveal, ready.more, 0.55);
      blurIn(reveal, ready.text, 0.65);
      blurIn(reveal, ready.cta, 0.75);
      blurIn(reveal, ready.scroll, 0.9);

      // The card floats, and tilts towards the pointer
      if (ready.image) {
        const image = ready.image;
        gsap.set(image, { transformPerspective: 1200 });
        gsap.fromTo(
          image,
          { yPercent: FLOAT.y, rotation: -FLOAT.turn },
          { yPercent: -FLOAT.y, rotation: FLOAT.turn, duration: FLOAT.duration, ease: "sine.inOut", yoyo: true, repeat: -1 },
        );
        const tiltY = gsap.quickTo(image, "rotationY", { duration: TILT.duration, ease: "power2.out" });
        const tiltX = gsap.quickTo(image, "rotationX", { duration: TILT.duration, ease: "power2.out" });
        const move = (e: PointerEvent) => {
          tiltY((e.clientX / innerWidth - 0.5) * 2 * TILT.y);
          tiltX(-(e.clientY / innerHeight - 0.5) * 2 * TILT.x);
        };
        window.addEventListener("pointermove", move);
        self.add(() => () => window.removeEventListener("pointermove", move));
      }

      // M3 · Through the portal
      let dark = false;
      let shown = false;
      const proxy = { p: 0 };
      gsap.to(proxy, {
        p: 1,
        ease: "none",
        onUpdate: () => {
          const p = proxy.p;
          s.p = p;
          hero.style.transform = `translateY(calc(${-COPY_RISE * seg(p, ...COPY_RISE_AT)} * var(--u)))`;
          const o = seg(p, ...READY_FADE);
          section.style.opacity = String(o);
          section.style.visibility = o > 0 ? "visible" : "hidden";
          if (p >= DARK_AT !== dark) {
            dark = p >= DARK_AT;
            setTheme(dark ? "dark" : "light");
          }
          if (p >= REVEAL_AT && !shown) {
            shown = true;
            reveal.timeScale(1).play();
          } else if (p < HIDE_AT && shown) {
            shown = false;
            reveal.timeScale(2).reverse();
          }
        },
        scrollTrigger: {
          trigger: mainEl,
          start: "top top",
          end: () => `+=${innerHeight * SCROLL_SCREENS}`,
          pin: true,
          scrub: SCRUB,
          invalidateOnRefresh: true,
        },
      });
    }, mainEl);

    return () => {
      ctx.revert();
      setTheme("light");
    };
  }, [loaded, reduced]);

  return (
    <>
      <Nav theme={theme} />
      <div>
        <main ref={main} className={styles.main}>
          <Preloader />
          <Portal state={state} scene={art?.scene ?? null} />
          <HeroCopy />
          <Ready product={art?.product ?? null} />
        </main>
      </div>
    </>
  );
}
