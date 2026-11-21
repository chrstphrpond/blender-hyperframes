# blender-hyperframes

A Claude Code skill. Claude builds and renders 3D shots in Blender, then edits the video in HyperFrames.

Written by Christopher Pond Maquidato, October 2026.

## Install on Windows

1. Clone it into your Claude skills folder. In PowerShell:

   ```powershell
   git clone https://github.com/chrstphrpond/blender-hyperframes "$HOME\.claude\skills\blender-hyperframes"
   ```

   You should now have `C:\Users\<you>\.claude\skills\blender-hyperframes\SKILL.md`. On macOS or Linux, clone into `~/.claude/skills/blender-hyperframes` and install Blender, FFmpeg, Node.js and uv with your package manager.

2. Install the tools, skipping any you already have, then open a new terminal:

   ```powershell
   winget install -e --id BlenderFoundation.Blender
   winget install -e --id Gyan.FFmpeg
   winget install -e --id OpenJS.NodeJS.LTS
   winget install -e --id astral-sh.uv
   ```

3. Install HyperFrames for Claude Code:

   ```powershell
   claude plugin marketplace add heygen-com/hyperframes
   claude plugin install hyperframes@hyperframes
   ```

4. Optional, for live control of an open Blender window:

   ```powershell
   claude mcp add blender uvx mcp-for-blender
   uvx mcp-for-blender install-addon
   ```

   Then in Blender, press N in the 3D viewport, open **MCP for Blender** and click **Start MCP Server**.

5. Start Claude Code and check the setup:

   ```powershell
   uv run --no-project "$HOME\.claude\skills\blender-hyperframes\scripts\bh.py" doctor
   ```

## Use

Ask Claude, for example:

- "Make a 10-second product ad for an amber perfume bottle in Blender, with a title and a vertical version."
- "Turn this sketch into a 3D character turntable and cut it with captions."

Claude writes a shot list first, builds each shot as a Blender script, shows preview stills and a contact sheet, then renders and edits in HyperFrames.

## Inside

- `SKILL.md`: the workflow Claude follows.
- `scripts/bh.py`: one helper CLI that finds Blender and runs `doctor`, `build`, `stats`, `render`, `sheet`, `encode` and `polyhaven`.
- `scripts/blender_job.py`: runs inside Blender for stats and renders.
- `scripts/bh_scene.py`: helpers for scene build scripts.
- `templates/build_scene.py`: a starting product shot.
- `references/`: build rules from Claude + Blender creators, and the HyperFrames handoff.
