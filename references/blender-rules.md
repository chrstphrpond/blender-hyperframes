# Blender rules and recipes

Collected from public X posts (October 2026) by people building with Claude + Blender. The quotes are theirs; the source is under each rule.

## Working rules

**Brief first.** "specify the shots, expressions, camera moves and final pose before building the scene." One character, one setting, one visual joke.
Source: @beamnxw, x.com/beamnxw/status/2113275303808160226

**Pull assets, arrange them; don't model everything.** "never let opus build a chair from scratch. it burns tokens and still looks fake. pull the asset and let opus arrange it."
- Use Poly Haven (`bh polyhaven`, CC0), MCP for Blender's `search_assets`, or BlenderKit.
- Render a 480p preview before the final.

Source: @rewind02, x.com/rewind02/status/2109661035036635291

**Models as code, part by part.**
- Send 2-3 references and a short brief, then build in order: "boots > suit > helmet > gloves > tank".
- Rig in a separate script, with extra bones for props.
- Bake materials into one 1024 texture atlas.
- Export one FBX with the rig, the mesh and every clip.
- "pick a style that fits code". Describe how a model should feel, not how to build it.

Source: @rewind02, x.com/rewind02/status/2111393368097849615

**Match a reference with a fixed camera.**
- Build in this order: shell, big furniture, clutter, close-up detail, then materials and light.
- "keep the reference camera fixed the whole time"
- "fix one thing per prompt"

Source: @rewind02, x.com/rewind02/status/2112890224426553836

**Build a kit, not a town.** Model walls, roofs, doors and windows as a modular kit, combine them into 5-10 variants, then place them in code. "make 10 good house variants and let code place 500."
Source: @rewind02, x.com/rewind02/status/2113275919213142431

**Parametric scenes.** "Keep the geometry modular and expose the main parameters so I can regenerate variations without remodeling everything."
Source: @Lummox_eth, x.com/Lummox_eth/status/2112506918883274819

**Characters from a picture.**
- Start from one front view in a T-pose, with no accessories.
- A generator (Tripo or Meshy, paid) makes the mesh and skeleton.
- Ask for poses by name; Claude writes the Python.
- Glasses, laptops and hats are separate objects, never baked into the body. Starting arms-down tore the hoodie when the arms were raised.

Source: @coldcat_ai, x.com/coldcat_ai/status/2112192313153728793

**Review with numbers, and with someone else's eyes** (translated from Japanese).
- Show Claude its own render and have it measure the result in numbers.
- Let a separate model that did not build the scene do the scoring.
- Research how the real thing behaves; the example was how leaves actually fall.
- Project tree shadows instead of painting dappled light.

Source: @KanaWorks_AI, x.com/KanaWorks_AI/status/2108740421514076433

**2D first, then 3D.** Animate in 2D code first, then give that code to a second Claude to rebuild the same timing in Blender. Because the film is code, the choreography carries over exactly.
Source: @kevin_t_ngo, x.com/kevin_t_ngo/status/2108582192481992922

**Cheap previews.** "the skill to learn now is briefing the agent, checking cheap previews and knowing what to fix before the expensive render."
Source: @kenonews, x.com/kenonews/status/2113225121703846338

**Small rounds of feedback** (translated). Clear instructions, feedback in small pieces, background motion made inside Blender, everything rendered in EEVEE.
Source: @VJ_keori, x.com/VJ_keori/status/2114255468722053223

## Recipes

**CGI product ad, 15 s.**
1. Brief to shot list.
2. Build the bottle, liquid and cap from code.
3. Light with a Poly Haven HDRI.
4. Render 4 shots.
5. Titles and the cut in HyperFrames.
6. Deliver 16:9, 9:16 and 1:1, each rendered at its own size.

Start from `templates/build_scene.py`.
Source: @Y0urDumble, x.com/Y0urDumble/status/2114084322227503206

**Character short.**
1. Director's brief.
2. Block out the character and set.
3. Add the walk, eye moves and close-ups.
4. Light with a Poly Haven HDRI.
5. Assemble, with titles and audio, in HyperFrames.

Source: @beamnxw (with Remotion; HyperFrames fills that role here).

**Game asset.** Build, rig, animate the clips (idle, walk, action), bake the atlas and export FBX or glTF. A turntable render through this skill makes the showcase clip.

**Gaussian splat to an editable scene.** gokayfem/gaussian-splat-to-blender-nodes (MIT) rebuilds a splat as Geometry Nodes and Shader Nodes. Its author says it is "not insanely accurate". Use it as a blockout.
gokayfem/video-to-blender turns a reference video or image into a procedural node setup.

## Blender versions

- `bh_scene.setup()` and `blender_job.py` pick `BLENDER_EEVEE` (5.x) or `BLENDER_EEVEE_NEXT` (4.2-4.x) automatically.
- Blender 4.4+ keeps animation curves in action layers. The template's `set_ease()` handles both layouts.
- In EEVEE, glass with transmission shows dither noise at low samples. Preview it opaque, or raise samples for the final, or use Cycles for that shot.
