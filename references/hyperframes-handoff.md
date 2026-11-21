# Blender clips in HyperFrames

Checked against the HyperFrames 0.8.140 plugin docs and an actual render (27 Oct 2026). For anything not covered here, the HyperFrames skill is the authority.

## Formats

| Shot | Encode | Notes |
|---|---|---|
| Opaque | `bh encode DIR --out video/assets/x.mp4` | H.264, yuv420p, `-g` = fps. HyperFrames' own advice: sources with a keyframe interval over about 1 s freeze on seek. |
| Cutout over other layers | render `--transparent --hide Floor`, then `bh encode DIR --out video/assets/x --alpha webm` | VP9 with alpha. Tested: composites over lower layers in the render. Preview uses a VP8 proxy; the render decodes the original. |
| Editor master with alpha | `--alpha mov` | ProRes 4444. Accepted as input (proxied for preview). Large files. |
| PNG sequence | not accepted as input | Encode first. |

## Placing a clip

```html
<video id="shot01" class="clip" src="assets/shot01.mp4" muted playsinline
       data-start="0" data-duration="5" data-track-index="0"></video>
```

- `id` is required on every `<video>` and `<audio>`.
- A silent clip needs `muted`; a clip with sound uses `data-has-audio="true"`. One with neither fails lint (`video_missing_muted`).
- `data-media-start` is the in-point in seconds. There is no out-point attribute; `data-duration` sets the length.
- Don't call `play()`, `pause()` or seek. Don't add `crossorigin`. Don't animate the video's width or height; animate a wrapper.
- Don't put `data-start` on both a wrapper and the `<video>` inside it (`video_nested_in_timed_element`).

## Composition basics

- The root `<div>` needs `data-composition-id`, `data-width`, `data-height`, plus `data-duration` (the render length).
- The GSAP timeline is created paused and registered as `window.__timelines["<id>"]`.
- A standalone `index.html` root sits directly in `<body>`, with no `<template>`.
- Lint warns (`nested_structure_needs_subcomposition`) when a timed section holds nested elements. Move titles and cards into sub-compositions as the HyperFrames skill describes.

## CLI

- With the plugin, run the CLI through the plugin's `plugin-cli.mjs`, as the HyperFrames skill says.
- With standalone skills, use `npx hyperframes`.
- Commands:
  - `init <dir> --resolution landscape|portrait|square`
  - `lint`
  - `check` (the final gate; `validate`, `inspect` and `layout` are deprecated aliases)
  - `preview`
  - `render -o out.mp4 --quality draft|standard|high --fps 30`
- There is no aspect flag; the root's `data-width` and `data-height` set it.
- Needs Node 22+ and FFmpeg. `hyperframes browser ensure` fetches its Chrome, and `hyperframes doctor` checks the setup.

## Tested

- 27 Oct 2026, macOS. Blender 5.2.3 LTS (bpy module), EEVEE, preview at 960x540.
- Clips: a 150-frame MP4, and a 60-frame alpha WebM with the floor hidden.
- HyperFrames 0.8.140 draft render of a 7 s, 1920x1080 composition: done in 17.8 s. The cutout sat cleanly over a solid HyperFrames layer, with GSAP text on top.
