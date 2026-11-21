"""Runs inside Blender. Called by bh.py; usable directly:

    blender -b scene.blend --python-exit-code 1 -P blender_job.py -- stats
    blender -b scene.blend --python-exit-code 1 -P blender_job.py -- render --out renders/shot01 --preview

Renders are always PNG frames (frame_0001.png ...). bh.py encodes them, so output
does not depend on Blender's changing video settings.
"""

import argparse
import json
import sys
from pathlib import Path

import bpy


def engine_id(name):
    """Map eevee/cycles/workbench to whatever this Blender version calls it."""
    available = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    wanted = {
        "eevee": ["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"],  # 5.x and 4.2-4.x
        "cycles": ["CYCLES"],
        "workbench": ["BLENDER_WORKBENCH"],
    }[name]
    for ident in wanted:
        if ident in available:
            return ident
    raise SystemExit(f"render engine {name} not available; this Blender offers {available}")


def parse_frames(text, scene):
    if not text:
        return scene.frame_start, scene.frame_end
    a, _, b = text.partition("-")
    return int(a), int(b or a)


def stats(_args):
    scene = bpy.context.scene
    r = scene.render
    objs = []
    for o in scene.objects:
        row = {"name": o.name, "type": o.type, "location": [round(v, 3) for v in o.location],
               "hidden_render": o.hide_render}
        if o.type == "MESH":
            row["polys"] = len(o.data.polygons)
            row["materials"] = [s.material.name for s in o.material_slots if s.material]
        if o.parent:
            row["parent"] = o.parent.name
        if o.animation_data and o.animation_data.action:
            row["action"] = o.animation_data.action.name
        objs.append(row)
    world = scene.world
    out = {
        "blender": bpy.app.version_string,
        "file": bpy.data.filepath or None,
        "engine": r.engine,
        "resolution": [r.resolution_x, r.resolution_y, r.resolution_percentage],
        "fps": r.fps / r.fps_base,
        "frames": [scene.frame_start, scene.frame_end],
        "camera": scene.camera.name if scene.camera else None,
        "film_transparent": r.film_transparent,
        "world_nodes": [n.type for n in world.node_tree.nodes] if world and world.use_nodes else [],
        "counts": {"objects": len(scene.objects), "polys": sum(o.get("polys", 0) for o in objs),
                   "materials": len(bpy.data.materials), "images": len(bpy.data.images)},
        "objects": objs,
    }
    print("BH_JSON " + json.dumps(out))


def render(a):
    scene = bpy.context.scene
    r = scene.render
    if not scene.camera:
        raise SystemExit("scene has no active camera")
    r.engine = engine_id(a.engine)
    if a.res:
        w, _, h = a.res.lower().partition("x")
        r.resolution_x, r.resolution_y = int(w), int(h)
    r.resolution_percentage = a.percent or (50 if a.preview else 100)
    samples = a.samples or (16 if a.preview else None)
    if samples:
        if r.engine == "CYCLES":
            scene.cycles.samples = samples
        elif r.engine.startswith("BLENDER_EEVEE"):
            scene.eevee.taa_render_samples = samples
    if a.fps:
        r.fps, r.fps_base = a.fps, 1.0
    r.film_transparent = a.transparent
    for name in filter(None, (a.hide or "").split(",")):  # e.g. the floor, for a cutout over other layers
        obj = scene.objects.get(name.strip())
        if not obj:
            raise SystemExit(f"--hide: no object named {name.strip()}")
        obj.hide_render = True
    settings = r.image_settings
    settings.file_format = "PNG"
    settings.color_mode = "RGBA" if a.transparent else "RGB"
    settings.color_depth = "8"
    r.use_file_extension = True
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    if a.stills:
        frames = [int(f) for f in a.stills.split(",") if f.strip()]
        for f in frames:
            scene.frame_set(f)
            r.filepath = str(out / f"frame_{f:04d}")
            bpy.ops.render.render(write_still=True)
    else:
        start, end = parse_frames(a.frames, scene)
        scene.frame_start, scene.frame_end = start, end
        r.filepath = str(out / "frame_####")
        bpy.ops.render.render(animation=True)
        frames = list(range(start, end + 1))
    print("BH_JSON " + json.dumps({
        "out": str(out), "frames": frames if a.stills else [frames[0], frames[-1]], "engine": r.engine,
        "size": [r.resolution_x * r.resolution_percentage // 100, r.resolution_y * r.resolution_percentage // 100],
        "fps": r.fps / r.fps_base, "transparent": a.transparent,
    }))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="blender_job.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stats").set_defaults(fn=stats)
    p = sub.add_parser("render")
    p.add_argument("--out", required=True)
    p.add_argument("--preview", action="store_true", help="50%% size and 16 samples unless set")
    p.add_argument("--engine", choices=["eevee", "cycles", "workbench"], default="eevee")
    p.add_argument("--res", help="WIDTHxHEIGHT, e.g. 1920x1080")
    p.add_argument("--percent", type=int)
    p.add_argument("--samples", type=int)
    p.add_argument("--fps", type=int)
    p.add_argument("--frames", help="START-END, default the scene range")
    p.add_argument("--stills", help="comma-separated frames to render as stills, e.g. 1,60,120")
    p.add_argument("--transparent", action="store_true", help="transparent film, RGBA PNG")
    p.add_argument("--hide", help="comma-separated object names to leave out of this render")
    p.set_defaults(fn=render)
    a = ap.parse_args(argv)
    a.fn(a)


main()
