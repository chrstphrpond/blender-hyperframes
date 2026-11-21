"""Starting scene: a product on a plinth with a slow camera orbit. Copy it, then change PARAMS and build().

    python <skill>/scripts/bh.py build scene/build_scene.py -- --out scene/scene.blend [--hdri assets/x/x_2k.hdr]

The whole scene is code: rerun the script after every change instead of editing the .blend by hand,
so any shot can be rebuilt, varied and reviewed.
"""

import argparse
import math
import os
import sys
from pathlib import Path

# bh.py sets BH_SCRIPTS to the skill's scripts folder; the fallback works when run from the skill itself
sys.path.insert(0, os.environ.get("BH_SCRIPTS") or str(Path(__file__).resolve().parent.parent / "scripts"))

import bpy  # noqa: E402
from bh_scene import area_light, camera, hdri_world, keyframe, material, reset, save, seed, setup  # noqa: E402

PARAMS = {
    "seconds": 5.0,
    "fps": 30,
    "size": (1920, 1080),
    "product_color": (0.55, 0.22, 0.04, 1.0),  # amber
    "cap_color": (0.83, 0.69, 0.22, 1.0),  # gold
    "orbit_degrees": 60,  # how far the camera travels around the product
    "lens": 50,
}


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="scene/scene.blend")
    ap.add_argument("--hdri", help="HDRI file; without it a three-point light rig is used")
    ap.add_argument("--seconds", type=float, default=PARAMS["seconds"])
    ap.add_argument("--vertical", action="store_true", help="1080x1920 instead of 1920x1080")
    return ap.parse_args(argv)


def build(a):
    reset()
    seed(7)
    w, h = PARAMS["size"]
    scene = setup(*((h, w) if a.vertical else (w, h)), fps=PARAMS["fps"], seconds=a.seconds)

    # plinth
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1.4, depth=0.4, location=(0, 0, 0.2))
    plinth = bpy.context.object
    plinth.name = "Plinth"
    bevel = plinth.modifiers.new("Bevel", "BEVEL")
    bevel.width, bevel.segments = 0.03, 4
    plinth.data.materials.append(material("Stone", (0.82, 0.8, 0.77, 1), roughness=0.6))
    bpy.ops.object.shade_smooth()

    # product: bottle body and cap, built part by part
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.42, depth=1.3, location=(0, 0, 1.05))
    body = bpy.context.object
    body.name = "Bottle"
    body.modifiers.new("Bevel", "BEVEL").width = 0.12
    body.modifiers["Bevel"].segments = 8
    body.data.materials.append(material("Amber", PARAMS["product_color"], roughness=0.12))
    bpy.ops.object.shade_smooth()

    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.18, depth=0.32, location=(0, 0, 1.86))
    cap = bpy.context.object
    cap.name = "Cap"
    cap.data.materials.append(material("Gold", PARAMS["cap_color"], metallic=1.0, roughness=0.25))
    bpy.ops.object.shade_smooth()

    # floor that catches shadows
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    floor = bpy.context.object
    floor.name = "Floor"
    floor.data.materials.append(material("Floor", (0.12, 0.12, 0.13, 1), roughness=0.4))

    # light
    if a.hdri:
        hdri_world(a.hdri, strength=1.0)
    else:
        world = bpy.data.worlds.new("World")
        world.use_nodes = True
        world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.02, 0.025, 1)
        scene.world = world
        area_light((3.5, -3.0, 4.0), power=900, size=3, name="Key")
        area_light((-4.0, -2.0, 2.5), power=300, size=4, name="Fill")
        area_light((0.0, 4.0, 3.5), power=700, size=2, name="Rim")

    # camera on an orbit: an empty at the product turns, the camera rides along
    pivot = bpy.data.objects.new("Orbit", None)
    scene.collection.objects.link(pivot)
    pivot.location = (0, 0, 1.0)
    cam = camera(location=(0, -6.5, 2.2), target=(0, 0, 1.1), lens=PARAMS["lens"])
    cam.parent = pivot
    cam.location = (0, -6.5, 1.2)
    half = math.radians(PARAMS["orbit_degrees"] / 2)
    keyframe(pivot, scene.frame_start, rotation_euler=(0, 0, -half))
    keyframe(pivot, scene.frame_end, rotation_euler=(0, 0, half))
    if pivot.animation_data and pivot.animation_data.action:
        set_ease(pivot.animation_data.action)
    return scene


def set_ease(action):
    """Ease in and out on every key (Blender 4.4+ keeps curves in layers/channelbags)."""
    curves = list(getattr(action, "fcurves", []) or [])
    if not curves and hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    curves += list(bag.fcurves)
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.easing = "AUTO"


if __name__ == "__main__":
    a = args()
    build(a)
    print("saved", save(a.out))
