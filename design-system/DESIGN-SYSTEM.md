# Pranav’s website design system

Exported 5 November 2026 from the Personal-Site source. This is a portable visual reference for future projects, independent of the portfolio’s content and hosting.

## Instructions for a future coding assistant

Use this file as the visual specification when the user asks to reuse Pranav’s personal-site design. Read `reference-styles.css` for exact selectors, sizes, states, responsive rules, and animations. Preserve the typography, palette, generous spacing, understated borders, floating navigation, and scientific visual language. Adapt the layout and content to the new project. Do not copy personal details, project descriptions, contact endpoints, domain names, or deployment configuration unless requested.

The stylesheet is a snapshot, not a dependency of the original application. Changes to the original site do not automatically update this export. The Markdown and CSS together are the source of truth; this guide summarizes the most reusable decisions.

## Visual direction

Quiet, precise, contemporary, and research-inspired. Cool off-white surfaces, charcoal text, muted blue accents, thin borders, and generous whitespace. Pair an immersive dark navy hero with lighter content sections. Use scientific diagrams, dot grids, contour lines, networks, or abstract data plots as subtle decoration. Keep backgrounds low contrast and behind readable content. Avoid introducing unrelated bright colours or heavy card shadows.

## Fonts

| Role | Font | Usage |
| --- | --- | --- |
| Headings | Sora, Arial, sans-serif | h1/h2; mostly weight 500 with tight tracking |
| Body and controls | Inter, Arial, sans-serif | Paragraphs, navigation, buttons, metadata, forms |
| Metadata | Inter | The existing `.mono` class is 12px Inter, despite its name |

Load these fonts in the document head:

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,450;0,500;0,550;0,600;0,650;0,700;0,800;1,500&family=Sora:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
```

Font files are not bundled. The font link requires network access; Arial/sans-serif are fallbacks. For offline use, obtain licensed font files and self-host them separately.

| Element | Size | Weight / line-height / tracking |
| --- | --- | --- |
| h1 | clamp(44px, 5.5vw, 76px) | 500 / 1.13 / -0.055em |
| h2 | clamp(31px, 3.25vw, 43px) | 500 / 1.2 / -0.055em |
| h3 | 21px | 500 / default / -0.035em |
| Hero greeting | clamp(46px, 6.2vw, 86px) | 650; strong 800 / 1.15 / -0.065em |
| Hero secondary text | clamp(23px, 2.4vw, 34px) | 400 / 1.35 / -0.045em |
| Project body | 14px | 400 / 1.8 |
| Buttons | 14px | 500 |
| Tags | 11px | 400 |

Emphasized words (`em`) use the blue accent and normal font style rather than italics. Body paragraphs generally use line-height 1.75. Preserve the responsive overrides in the reference CSS when reproducing a page exactly.

## Colours

| Token / role | Value |
| --- | --- |
| `--paper`: page background | #f7f8fa |
| `--ink`: primary text / dark buttons | #222833 |
| `--muted`: supporting text | #68717e |
| `--line`: borders / dividers | #dde1e7 |
| `--accent`: emphasis / focus | #4969a1 |
| Hero background | #172332 |
| Hero foreground | #f6f8fc |
| Hero secondary text | #c7d2e4 |
| Hero emphasis | #a4d6d2 |
| Hero intro | #d0d9e7 |
| Navigation pill background | #252e3e |
| Navigation pill border | #354056 |
| Dark button hover | #3c4c66 |
| Outline button border | #cbd5e3 |
| Soft hover surface | #e7edf6 |
| Translucent panel | #ffffffed |
| Form border | #d9e1ec |
| Muted section surface | #eef0f4ed |
| Project illustration background / foreground | #e8edf4 / #397c91 |
| Purple illustration background / foreground | #ecebf3 / #6b67b8 |
| Teal illustration background / foreground | #e8edf0 / #427b8b |
| Tag text | #526f86 |
| Status dot | #0d838f |
| Text selection | #bcdfe4 |

Eight-digit hex values include alpha; retain their transparency. All additional shades and gradient stops are preserved in `reference-styles.css` and the exported background components.

## Layout and spacing

- Main container: max-width 1320px; width `calc(100% - 112px)` (56px side gutters).
- At 1100px or less: 36px side gutters; at 800px or less: 24px; at 600px or less: 20px.
- Standard section padding: 75px top and bottom; section headers pair a heading with an optional text link.
- Project grid: three equal columns with 28px gaps on desktop; use the existing media rules for smaller screens.
- Hero: at least 100svh, centered introduction, actions and supporting text toward the bottom. For short viewports (height at most 600px), minimum height is 600px.
- Contact: max-width 1100px; form on the left, social links on the right. Grid columns `minmax(0, 2fr) minmax(190px, 1fr)`; gap `clamp(24px, 4vw, 56px)`. Stack at 600px or less.
- Responsive breakpoints: 1100px, 800px, 600px; illustration height increases at 1500px.

## Components

**Floating navigation:** fixed 16px from the top on desktop; translucent near-white panel, 78px height, 22px radius, 20px backdrop blur, thin border, soft shadow. Inside it, use a dark rounded navigation pill. The original application hides navigation on scroll and reveals it near the top edge or on focus; that interaction lives in the application, not in CSS alone.

**Buttons:** inline-flex with centered content, 25px gap, minimum height 49px, padding 15px 21px, radius 8px. Dark variant uses ink/paper. Outline variant uses paper with a pale blue-grey border. Transition background and text colour over 0.2s. Hero buttons invert to a pale surface.

**Text links:** inline-flex, 16px gap, 8px vertical padding, thin bottom border; hover turns both text and border accent blue. Use small line arrows with consistent strokes.

**Project cards:** open layout with an abstract illustration, small category label, title, description, and outlined technology tags. Illustration height 241px (270px at large desktop). Keep content backgrounds quiet and avoid enclosing every card in a heavy panel. Tags use 6px 9px padding, 7px gaps, thin borders.

**Forms:** near-white translucent surface; 35px padding, 18px radius, #d9e1ec border, subtle shadow `0 10px 40px #31446607`. Name and email share a row on desktop with 22px gap. Labels remain visible. Fields stack on mobile; input font size becomes 16px. Preserve validation, focus, disabled, loading, and success states when implementing form behaviour.

**Supporting sections:** pale blue-grey bands with thin top/bottom borders. Technology tiles use white backgrounds, thin borders, 32px icons, compact names and muted descriptions.

## Motion and accessibility

- Background network drift: 22 seconds, ease-in-out, alternating; node pulse: 6 seconds.
- Section reveal: opacity and 18px vertical translation, 0.65 seconds. CSS `.reveal` requires code to add `.revealed`; do not hide content without that behaviour.
- Navigation transitions: transform 0.28s, opacity 0.22s.
- Focus indicators: 2px accent outline with 5px offset. Maintain keyboard access and visible labels.
- Honour `prefers-reduced-motion`: disable animation/transitions, smooth scrolling, hidden reveal states, and deliberate loader delay.
- Treat background diagrams as decorative (`aria-hidden`, no pointer interactions). The exported React components retain their existing reduced-motion behaviour.

## Files and reuse

- `DESIGN-SYSTEM.md`: reusable instructions and visual specification.
- `reference-styles.css`: complete original stylesheet, including responsive styles, loader, hover/focus states, and animations.
- `components/DescentBackground.jsx`: animated canvas loss contours and gradient-descent trajectories.
- `components/NetworkBackground.jsx`: decorative SVG background.
- `components/PageLoader.jsx`: optional 2–4–2 loading animation. It uses a 1.4-second minimum delay in the original design; carrying that delay into a different project is optional.

The React components require React and the matching CSS classes. The CSS includes page-specific selectors and global element rules: review and adapt it before importing it into an existing application. The full application markup, navigation controller, form delivery code, personal assets, and font binaries are intentionally outside this visual export.

To reuse in another Codex chat, attach this Markdown file and the ZIP, or point the assistant to this folder, and say:

> Use Pranav’s website design system as the visual reference for this project. Read DESIGN-SYSTEM.md, reuse the palette and typography, and adapt the exported styles and decorative components to the new content.

This file supplies the reference across projects; do not assume a future chat automatically has access to the original conversation.
