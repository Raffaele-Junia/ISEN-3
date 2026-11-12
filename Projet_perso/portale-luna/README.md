# portale-luna — website

A two-screen site by ubernatural (uberdesigner.ai), for a fictional private-compute service for teams that train large models, called "Luna". The first screen is the surface of the moon: a cratered grey plain under a low, hard sun, a black sky full of stars with the Earth up on the right, and a tall black monolith standing on the plain like a portal, throwing a long shadow; the access card's light (a white edge, a chip, the name and a number) glows on its face.
Scrolling turns the slab to face you, lights it up white and flies through it into the second screen, where the card
floats between two headlines. The picture and the card are drawn in code: there is no photo and no render.
It shares its mechanics (the preloader, the intro and the scroll through the portal) with the portale template.

## Run it

```bash
npm install
npm run dev
```

## What's where

```
src/content/luna.ts          the brand, all the copy, the tokens it changes, the scene's shader, the product card
src/lib/scene.ts              ray-traces the picture once with fragment shaders; gives the slab's corners
src/lib/product.ts            draws the card on the second screen
src/styles/tokens.css         every color, size and font
src/components/Page.tsx       loading, the intro timeline and the scroll transition (GSAP + ScrollTrigger)
src/components/Portal.tsx     the picture, the card's light mapped onto the slab, the portal it turns into
src/components/               HeroCopy, Ready (second screen), Nav, Preloader, Wordmark, Cursor
```

Fonts: Geist, from Google Fonts under the SIL Open Font License.
