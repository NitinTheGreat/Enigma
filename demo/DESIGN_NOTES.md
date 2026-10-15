# Demo design notes

Written before any demo code, from a reading of the ConjunctionTriage web app
at `F:\conjunction-triage\web`. That folder is the live frontend; the older
`frontend/` folder beside it is a vanilla JavaScript dashboard that `web/`
replaced, and it is not the reference.

## 1. What ConjunctionTriage is built with

| Aspect | ConjunctionTriage | Demo |
| --- | --- | --- |
| Framework | Next.js 16.3.4, App Router, React 19.2.8 | same, pinned to the same versions |
| Build tool | `next build`, Turbopack | same, with `output: "export"` for a static bundle |
| Styling | plain global CSS with custom properties in `app/globals.css`, one CSS file per component | same |
| Component library | none; hand built components, `lucide-react` 0.577.0 icons | same |
| Motion | GSAP 3.15.0 with `@gsap/react` 2.1.2, `useMotion()` honouring `prefers-reduced-motion` plus a stored override | same hook, same rule |
| Fonts | Fontsource, self hosted from npm, no CDN | same three packages |
| 3D | three.js globe on the home page | **not used**; the hero is the pipeline diagram |

## 2. Layout and spacing

- Page gutter `clamp(22px, 4.2vw, 80px)`; content max width 1660px.
- Header 100px tall, single bottom rule in `--line`.
- Spacing steps in use: 4, 7, 12, 14, 20, 24, 26, 30, 50, 70, 90 px. Panels pad
  26px; stat columns pad 26px top and 30px sides; section headings sit 50px
  above content.
- Grids: two column field grid with 20px gap; three column headline stats
  separated by 1px vertical rules rather than gaps.
- Border radius **2px** everywhere. The only round shapes are 40px icon buttons
  and 4 to 5px dots.
- Shadows: **none** on cards. One shadow only, on dialogs:
  `0 30px 100px #10100c33`. Depth comes from 1px rules and the cream panel
  against the paper ground.
- A fixed fractal noise overlay at 2.5 % opacity gives the paper texture.

## 3. Typography

| Role | Family | Size | Weight | Letter spacing |
| --- | --- | --- | --- | --- |
| Body | Archivo Variable | 14px, line height 1.65 | 400 | normal |
| Headings h1 to h4 | Archivo Variable | per component | 450 | -0.05em, line height 1.1 |
| Page title | Archivo Variable | clamp(44px, 6vw, 90px) | 420 | -0.065em |
| Hero title | Archivo Variable | clamp(92px, 10.6vw, 172px) | 420 | -0.075em |
| Emphasis in headings | Instrument Serif italic | 1.15em of heading | 400 | -0.04em |
| Stat figure | Archivo Variable | clamp(40px, 4.6vw, 70px), tabular numerals | 450 | -0.065em |
| Eyebrow | IBM Plex Mono, uppercase | 9 to 10px | 400 | 0.08em |
| Mono labels, tags | IBM Plex Mono | 9 to 10px | 400 | 0.035 to 0.04em |
| Buttons | Archivo Variable | 11 to 12px | 500 | normal |

The demo keeps every family and weight. Sizes are scaled up for a projector:
body 16px, eyebrow 11px, because the reviewer will be several metres away.

## 4. Motion

| What | How | Duration, easing |
| --- | --- | --- |
| Route content enters | GSAP opacity 0 to 1, y 12 to 0 | 0.55s, `power2.out` |
| Dialog opens | opacity, y 25 to 0, scale 0.985 to 1 | 0.45s, `power3.out` |
| Dialog closes | opacity, y to 15 | 0.2s |
| Active nav dot | scale 0 to 1 | 0.6s, `back.out(2)` |
| Links, buttons | CSS colour, background, border | 0.2s |
| Button arrow | translate 2px, -2px on hover | 0.25s |

All motion is skipped when `prefers-reduced-motion` is set, or when the
viewer turns motion off, through `html[data-motion=reduced]`.

## 5. Recurring components, reused in the demo

- **Panel**: 1px `--line` border, `--cream` ground, 26px padding, no radius
  beyond 2px, no shadow.
- **Headline stats**: a top rule in `--ink`, columns split by 1px `--line`
  rules, a large tabular figure, then 12px muted caption.
- **Tiles**: stacked rows with a top `--ink` rule and `--line` separators.
- **Eyebrow**: mono uppercase label above every heading.
- **Tag**: mono 9px, uppercase, 1px border, 2px radius.
- **Buttons**: primary filled with `--acid`, dark filled with `--ink`, outline
  with `--line`; 48px tall, 2px radius, trailing arrow icon.
- **Tab switch**: text tabs with a 2px `--rust` underline on the active one.
- **Details drawer**: `details` with a top rule; reused as "Why this matters".
- **Notice**: 2px left border in `--olive` on a faint olive ground.

## 6. Palette mapping, old to new

Produced and checked by `scripts/demo_palette.py`, which exits non-zero if any
accent moves less than 40 degrees, if any accent comes within 40 degrees of a
semantic colour, or if any pair the demo uses fails WCAG AA. The full output is
in `demo/design/palette.json`.

ConjunctionTriage is a **light** design on warm parchment, so the paper tone
moves. Every neutral moves from the warm parchment family, about 43 degrees,
into a cool slate family at 248 degrees, with lightness held. Every accent
rotates by the same 250 degrees, which is a 110 degree shift for each, so the
accents keep their relationship to one another.

| Token | Used for | Old | New | Hue | Shift | Lightness |
| --- | --- | --- | --- | --- | --- | --- |
| `--paper` | page background | `#e8e4da` | `#dedde5` | 43 to 248 | 155 | 0.88 to 0.88 |
| `--cream` | panels, cards, drawer | `#f5f1e8` | `#eceaf3` | 42 to 253 | 148 | 0.94 to 0.94 |
| `--field` | inputs, raised surfaces | `#f8f5ec` | `#efeef6` | 45 to 248 | 158 | 0.95 to 0.95 |
| `--ink` | body text, headings, dark button | `#29261f` | `#222127` | 42 to 250 | 152 | 0.14 to 0.14 |
| `--muted` | secondary text, captions | `#726e60` | `#5e5d68` | 47 to 246 | 161 | 0.41 to 0.39 |
| `--line` | rules, borders, dividers | `#c8c3b5` | `#bab9c4` | 44 to 246 | 159 | 0.75 to 0.75 |
| `--dark` | presenter notes ground | `#25271e` | `#202025` | 73 to 240 | 167 | 0.14 to 0.14 |
| `--dark-hover` | dark button hover | `#464633` | `#383742` | 60 to 246 | 174 | 0.24 to 0.24 |
| `--dark-text` | secondary text on dark | `#b4b5a6` | `#aaa9b2` | 64 to 247 | 177 | 0.68 to 0.68 |
| `--dark-rule` | rules on dark | `#565847` | `#4c4a55` | 67 to 251 | 176 | 0.31 to 0.31 |
| `--olive` | brand mark, eyebrow markers | `#777b45` | `#7b456e` | 64 to 314 | 110 | 0.38 to 0.38 |
| `--acid` | primary button, selection | `#d0d68b` | `#d68bc3` | 65 to 315 | 110 | 0.69 to 0.69 |
| `--acid-hover` | primary button hover | `#dfe4a9` | `#e4a9d5` | 65 to 315 | 110 | 0.78 to 0.78 |
| `--rust` | focus ring, active tab, progress | `#b45436` | `#6936b4` | 14 to 264 | 110 | 0.46 to 0.46 |

One deliberate exception to "hold lightness": `--muted` moved from 0.41 to
0.39. Held exactly, it measured 4.37 against `--paper`, just under the 4.5 AA
threshold, so it was darkened by the smallest step that passes.

The new accents sit well clear of the semantic colours: plum and orchid at
314 to 315 degrees, and violet at 264 degrees, against the semantic red at 10,
green at 152 and blue at 207.

### Semantic colours, fixed by the paper and the video

| Meaning | Colour | How it may be used |
| --- | --- | --- |
| works, connected | `#2A6F4E` | text on cream, or a fill with cream text |
| inert | `#9E9B95` | **fill only, with ink text**; never as text |
| disconnected, defect | `#C84B31` | a fill with **white** text, a wire, a cross, or large type; never as body text |
| data, sensor | `#2B5B84` | text on cream, or a fill with cream text |

## 7. Contrast ratios for the pairs the demo uses

| Pair | Ratio | Needs | Use |
| --- | --- | --- | --- |
| ink `#222127` on paper `#dedde5` | 11.85 | 4.5 | body text on page |
| ink `#222127` on cream `#eceaf3` | 13.41 | 4.5 | body text on panel |
| muted `#5e5d68` on paper `#dedde5` | 4.81 | 4.5 | secondary text on page |
| muted `#5e5d68` on cream `#eceaf3` | 5.44 | 4.5 | secondary text on panel |
| ink `#222127` on acid `#d68bc3` | 6.34 | 4.5 | primary button label |
| cream `#eceaf3` on ink `#222127` | 13.41 | 4.5 | dark button label |
| cream `#eceaf3` on dark `#202025` | 13.62 | 4.5 | presenter notes text |
| dark-text `#aaa9b2` on dark `#202025` | 6.97 | 4.5 | secondary text on dark |
| olive `#7b456e` on paper `#dedde5` | 5.34 | 4.5 | accent text on page |
| works `#2A6F4E` on cream `#eceaf3` | 5.06 | 4.5 | verdict text, works |
| data `#2B5B84` on cream `#eceaf3` | 6.01 | 4.5 | sensor text and wires |
| cream `#eceaf3` on works `#2A6F4E` | 5.06 | 4.5 | label on a works fill |
| cream `#eceaf3` on data `#2B5B84` | 6.01 | 4.5 | label on a data fill |
| white `#ffffff` on disconnected `#C84B31` | 4.66 | 4.5 | label on a defect fill |
| ink `#222127` on inert `#9E9B95` | 5.76 | 4.5 | label on an inert fill |
| rust `#6936b4` on paper `#dedde5` | 5.59 | 3.0 | focus ring, active marker, non-text |
| disconnected `#C84B31` on cream `#eceaf3` | 3.91 | 3.0 | defect wire and cross, non-text |

The last row is the reason the defect red is never used for body text: at
3.91 it passes the 3.0 threshold for graphics and large type, and fails 4.5 for
normal text.

## 8. What the demo does not take from ConjunctionTriage

- The three.js Earth, the orbit mark, and any space imagery.
- The multi route site navigation. The demo is one page of seven screens,
  driven by the keyboard, because it is presented rather than browsed.
- The guide dialog's glossary. Its role is taken by hover tooltips on the
  five unavoidable terms, and by a "Why this matters" drawer on each screen.
