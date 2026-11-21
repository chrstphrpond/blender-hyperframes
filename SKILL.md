---
name: blender-hyperframes
description: Make 3D videos with Claude driving Blender and finishing the edit in HyperFrames - product and CGI ads, character shorts, game-asset turntables, 3D inserts for explainers. Builds each shot as a Blender Python script (headless, or live through MCP for Blender), checks cheap preview stills and contact sheets, renders PNG frames, encodes clips HyperFrames can seek (MP4, or alpha WebM cutouts), then adds titles, captions, audio and aspect ratios in HyperFrames. Use whenever a video needs 3D modelled, lit or animated in Blender, or the user mentions Blender with Claude.
---

# Blender + HyperFrames

Blender makes the shots; HyperFrames makes the video. Every shot is a script, so it can be rebuilt, varied and fixed one thing at a time.

`S` is this skill's folder. `bh` means `python S/scripts/bh.py`; without Python (common on Windows) use `uv run --no-project S/scripts/bh.py`. Every `bh` command prints JSON on success.

## 0. Setup, once per machine

1. `bh doctor`. Install what is marked MISS with the printed line (winget on Windows, brew on macOS), then open a new terminal.
   - Required: Blender 4.2+, FFmpeg, Node 22+, the HyperFrames skills.
   - Optional: MCP for Blender, for live work in an open Blender window.
2. If Blender is installed somewhere unusual, set `BLENDER` to the full path of `blender.exe` or the Blender binary.
3. MCP for Blender, only if the user wants live control:
   - Register it: `claude mcp add blender uvx mcp-for-blender`.
   - Install the add-on: `uvx mcp-for-blender install-addon`.
   - Restart Claude Code. In Blender, press N in the 3D viewport, open the **MCP for Blender** tab and click **Start MCP Server** if it isn't running.
   - Its tools: `execute_blender_code`, `look` (viewport, camera, multi-angle or frame strips), `get_scene_info`, `search_assets` / `import_asset` (Poly Haven, Sketchfab, Poly Pizza) and `generate_3d` (paid generators).
   - It sends an anonymous usage record by default. `DISABLE_TELEMETRY=true` in the server's env turns that off. Tell the user once.

## 1. Brief and shot list

Write `brief.md` in the project before touching Blender.

- One subject, one setting, one idea.
- For each shot, give:
  - id and seconds (2-6 s);
  - lens and camera move;
  - what happens, and the final pose or frame;
  - opaque, or cutout (rendered transparent and placed over HyperFrames layers);
  - what HyperFrames adds: title, caption, voice, music.
- Pick the frame rate once: 30 fps, the HyperFrames default, unless the user asks for 24 or 60. Set the size from the delivery: 1920x1080, or 1080x1920 for vertical. Render vertical natively; don't crop.
- Show the shot list and get a yes before building.

Project layout:

```
brief.md
scene/build_<shot>.py     the shot as code (edit this)
scene/<shot>.blend        output of the build; never hand-edited, always rebuilt
assets/                   downloaded assets, plus CREDITS.md with source and license
renders/<shot>/           PNG frames and sheet.jpg
video/                    the HyperFrames project; clips go in video/assets/
```

## 2. Build the shot as code

- **Headless (default):**
  - Copy `S/templates/build_scene.py` to `scene/build_<shot>.py`, change `PARAMS` and `build()`, then run `bh build scene/build_<shot>.py -- --out scene/<shot>.blend`.
  - Import helpers with `from bh_scene import ...`. They cover reset, seed, setup, camera, look_at, hdri_world, area_light, sun, material, import_asset, keyframe and save. `bh` puts them on the path.
- **Live (MCP for Blender):**
  - Use it to inspect, look through the camera and try ideas fast.
  - Fold whatever works back into the build script, so the shot can still be rebuilt from scratch.
  - Never call `reset()` in a live session: it clears the open file and refuses unless `force=True`.
- **Assets:**
  - `bh polyhaven list --type models|hdris|textures --query "<words>"`, then `bh polyhaven get <id> --res 2k --out assets/`. Everything there is CC0.
  - Load with `import_asset()` or `hdri_world()`, and add a line to `assets/CREDITS.md`.

Build rules (details and sources in `references/blender-rules.md`):

- Pull complex real objects (chairs, cars, plants) as assets. Model simple or stylized things in code, part by part, with a named object per part.
- Expose the main dimensions and counts as parameters, and seed all randomness.
- Keep accessories, props and moving parts as separate objects; rig in a separate script.
- For many similar things, build a small kit of variants and place them in code.
- Pick a look that suits code: clean shapes, strong materials and light beat fake photo-real detail.

## 3. Check before any long render

1. Run `bh stats scene/<shot>.blend`. Check the camera, frame range, poly counts and materials, and look for stray objects.
2. Run `bh render scene/<shot>.blend --out renders/<shot>-stills --preview --stills 1,<middle>,<last>` and read the PNGs against the brief.
3. Run `bh render scene/<shot>.blend --out renders/<shot> --preview`, then `bh sheet renders/<shot>`, and read `sheet.jpg`. Cell i shows frame `first + i * every`, from the JSON.
4. Fix one thing per round. Keep the camera fixed while fixing, so changes are easy to see.
5. For hero shots, a fresh subagent that did not build the scene scores the sheet against the brief, with numbers per point (framing, light, motion, materials). Fix the lowest score first.

## 4. Final render and encode

- Run `bh render scene/<shot>.blend --out renders/<shot>-final`. That's full size with the scene's samples on EEVEE.
- Use `--engine cycles --samples 128` only for glass, liquids or caustics, after a preview.
- Estimate before starting: preview time per frame x 4 (full size) x the sample ratio. If the estimate is over 10 minutes, tell the user and ask.
- **Opaque shot:** `bh encode renders/<shot>-final --out video/assets/<shot>.mp4`. This gives H.264 yuv420p with a keyframe every second, so HyperFrames seeks frame-accurately.
- **Cutout shot:** render with `--transparent --hide Floor` (plus any other backdrop objects), then `bh encode ... --alpha webm`. Tested: the alpha WebM composites over lower HyperFrames layers. Use `--alpha mov` (ProRes 4444) only when the user wants an editor file.
- Clip fps = composition fps (`--fps` on both `render` and `encode`).

## 5. Edit in HyperFrames

Load the HyperFrames skill (the `hyperframes` skill, or `/hyperframes:hyperframes` from the plugin) and follow its rules for structure, lint, check, preview and render. Handoff facts are in `references/hyperframes-handoff.md`. The essentials:

- `<video id="shot01" class="clip" src="assets/shot01.mp4" muted playsinline data-start="0" data-duration="5" data-track-index="0"></video>`.
  - `id` is required. A silent clip needs `muted`.
  - `data-media-start` trims the head; `data-duration` trims the tail.
- Don't play, pause or seek media in code, and don't animate a video's size. Animate a wrapper instead.
- Text, captions, logos and lower thirds belong in HyperFrames, not baked into the render. They stay sharp and editable.
- Each aspect ratio is its own composition with its own Blender render size.
- HyperFrames says to render the final only after the user approves the preview.

## 6. Report

Report the shot list with render times and engines, the files (`.blend`, clips, final videos), assets with licenses, and anything still rough. Offer the next fix as one line.

## Rules

- The scene is code. Change the script and rebuild, never the `.blend` by hand.
- Ask before paid services: `generate_3d` generators (Tripo, Meshy, Hyper3D Rodin, Hunyuan3D), Scenario, Sketchfab paid models.
- Credit every asset. Poly Haven is CC0; check other sources per asset.
- Don't recreate trademarked products, logos or real people unless the user owns them or says they have the rights.
