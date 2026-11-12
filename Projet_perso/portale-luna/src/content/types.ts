import type { ProductSpec } from "../lib/product";
import type { SceneSpec } from "../lib/scene";

/** Everything the page says and shows: the brand, the copy, the tokens it changes, the picture and the product. */
export type Content = {
  brand: string;
  title: string;
  description: string;
  /** Design tokens that differ from tokens.css, as CSS custom properties. */
  vars: Record<string, string>;
  nav: { links: string[]; heroActive: string; readyActive: string; account: string; cta: string };
  hero: { badge: string; lines: [string, string]; lead: string; primary: string; secondary: string };
  ready: { first: string; second: string; more: string; text: string; cta: string; scroll: string };
  card: { name: string; number: string }; // printed in light on the slab
  /** The picture behind the hero and the product on the second screen, both drawn in code. */
  art: { scene: SceneSpec; product: ProductSpec };
};
