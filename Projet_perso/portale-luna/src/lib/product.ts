// The product on the second screen, drawn in code in place of a render: a card lying at an angle on a
// transparent 16:9 canvas, returned as a decoded object URL.

export type ProductSpec = {
  from: string; // the card's colour at its near-left corner
  to: string; // and at its far-right corner
  mid?: string; // an optional colour between them
  ink: string; // the name and lines printed on it
  chip: [string, string]; // the chip's two tones
  line: string; // small print, bottom left
};

const W = 2880, H = 1620; // the canvas (the card box is 1600 × 900 design px)
const CARD = { w: 842, h: 524, r: 34, cx: 1440, cy: 838, turn: -30 }; // its size, centre and tilt (degrees) on the canvas

export async function drawProduct(spec: ProductSpec, brand: string): Promise<string> {
  await Promise.all(['400 1em "Geist"', '500 1em "Geist"'].map((f) => document.fonts.load(f)));
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("2D canvas unavailable");
  const { w, h, r } = CARD, x = -w / 2, y = -h / 2;
  ctx.translate(CARD.cx, CARD.cy);
  ctx.rotate((CARD.turn * Math.PI) / 180);

  // The body, with the soft shadow of something floating just off the page
  const body = ctx.createLinearGradient(x, -y, -x, y);
  body.addColorStop(0, spec.from);
  if (spec.mid) body.addColorStop(0.55, spec.mid);
  body.addColorStop(1, spec.to);
  ctx.save();
  ctx.shadowColor = "rgba(20, 30, 50, 0.16)";
  ctx.shadowBlur = 70;
  ctx.shadowOffsetY = 36;
  ctx.fillStyle = body;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fill();
  ctx.restore();

  ctx.save();
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.clip();
  // A band of light across it, and a fine grain so the surface isn't flat
  const sheen = ctx.createLinearGradient(x, y, -x * 0.4, -y);
  sheen.addColorStop(0.18, "rgba(255,255,255,0)");
  sheen.addColorStop(0.42, "rgba(255,255,255,0.22)");
  sheen.addColorStop(0.6, "rgba(255,255,255,0)");
  ctx.fillStyle = sheen;
  ctx.fillRect(x, y, w, h);
  for (let i = 0; i < 9000; i++) {
    ctx.fillStyle = Math.random() < 0.5 ? "rgba(255,255,255,0.035)" : "rgba(0,0,0,0.03)";
    ctx.fillRect(x + Math.random() * w, y + Math.random() * h, 1.6, 1.6);
  }
  ctx.restore();
  ctx.strokeStyle = "rgba(255,255,255,0.45)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(x + 1, y + 1, w - 2, h - 2, r - 1);
  ctx.stroke();

  // The chip
  const cw = 112, ch = 90, cx = x + 96, cy = -ch / 2 + 22;
  const chip = ctx.createLinearGradient(cx, cy, cx + cw, cy + ch);
  chip.addColorStop(0, spec.chip[0]);
  chip.addColorStop(1, spec.chip[1]);
  ctx.fillStyle = chip;
  ctx.beginPath();
  ctx.roundRect(cx, cy, cw, ch, 16);
  ctx.fill();
  ctx.strokeStyle = "rgba(0,0,0,0.22)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(cx + 34, cy + 22, cw - 68, ch - 44, 8);
  ctx.moveTo(cx, cy + 30); ctx.lineTo(cx + 34, cy + 30);
  ctx.moveTo(cx, cy + ch - 30); ctx.lineTo(cx + 34, cy + ch - 30);
  ctx.moveTo(cx + cw - 34, cy + 30); ctx.lineTo(cx + cw, cy + 30);
  ctx.moveTo(cx + cw - 34, cy + ch - 30); ctx.lineTo(cx + cw, cy + ch - 30);
  ctx.moveTo(cx + cw / 2, cy); ctx.lineTo(cx + cw / 2, cy + 22);
  ctx.moveTo(cx + cw / 2, cy + ch - 22); ctx.lineTo(cx + cw / 2, cy + ch);
  ctx.stroke();

  // The name, top right, after a small ring; small print bottom left
  ctx.fillStyle = spec.ink;
  ctx.strokeStyle = spec.ink;
  ctx.textBaseline = "alphabetic";
  ctx.textAlign = "right";
  ctx.font = '500 46px "Geist", sans-serif';
  if ("letterSpacing" in ctx) ctx.letterSpacing = "9px";
  const name = brand.toUpperCase(), right = -x - 66, base = y + 100;
  ctx.fillText(name, right + 9, base);
  const tw = ctx.measureText(name).width;
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.arc(right - tw - 34, base - 16, 15, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(right - tw - 34, base - 16, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.textAlign = "left";
  ctx.font = '400 25px "Geist", sans-serif';
  if ("letterSpacing" in ctx) ctx.letterSpacing = "3px";
  ctx.globalAlpha = 0.75;
  ctx.fillText(spec.line, x + 96, -y - 64);

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/webp", 0.95));
  if (!blob) throw new Error("The card could not be encoded");
  const url = URL.createObjectURL(blob);
  const img = new Image();
  img.src = url;
  await img.decode();
  return url;
}
