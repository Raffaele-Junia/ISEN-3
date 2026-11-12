import type { ComponentProps } from "react";
import { CONTENT } from "../content";

/**
 * The giant pale wordmark behind the preloader and the second screen: the brand's name set in type and stretched
 * to a 1400 × 192 box, its capitals the full height, fill --steel.
 */
export function Wordmark(props: ComponentProps<"svg">) {
  return (
    <svg viewBox="0 0 1400 192" aria-hidden="true" {...props}>
      <text
        x="0"
        y="192"
        fontSize={192 / 0.71}
        fontWeight="500"
        textLength="1400"
        lengthAdjust="spacingAndGlyphs"
        fill="var(--steel)"
        style={{ fontFamily: "var(--font-sans)" }}
      >
        {CONTENT.brand.toUpperCase()}
      </text>
    </svg>
  );
}
