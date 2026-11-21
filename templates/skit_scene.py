"""Low-poly skit: a block buddy and a faceted dev, tiny, standing on a giant laptop at night.

    python <skill>/scripts/bh.py build scene/skit_scene.py -- --out scene/skit.blend --timing video/assets/voice/timing.json

The look follows the "Claude, ..." comedy skits on TikTok (see references/style-lowpoly-skit.md): flat-shaded
characters, a dark keyboard deck, a glowing screen and a night window full of city lights, warm key light
against cool blue, shallow depth of field and bloom. With --timing (from `bh.py voices`) every spoken line
makes its speaker talk and cuts to that speaker's camera; without it a short demo timeline is used.
"""

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

# bh.py sets BH_SCRIPTS to the skill's scripts folder; the fallback works when run from the skill itself
sys.path.insert(0, os.environ.get("BH_SCRIPTS") or str(Path(__file__).resolve().parent.parent / "scripts"))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from bh_scene import (area_light, bloom, camera, color_look, cut_to, dof, facet, fcurves, flat, keyframe,  # noqa: E402
                      look_at, material, reset, save, seed, setup)

PARAMS = {
    "fps": 30,
    "size": (1080, 1920),  # vertical; --horizontal swaps it
    "buddy_color": (0.69, 0.19, 0.095, 1),  # terracotta
    "hoodie_color": (0.02, 0.05, 0.38, 1),
    "skin_color": (0.62, 0.38, 0.26, 1),
    "hair_color": (0.012, 0.012, 0.03, 1),
    "deck_color": (0.007, 0.009, 0.02, 1),
    "warm": (1.0, 0.52, 0.25),
    "cool": (0.33, 0.43, 1.0),
    "dev_at": (-1.3, 0.3),
    "buddy_at": (1.2, 0.5),
}

DEMO = [("dev", 0.4, 1.9), ("buddy", 2.2, 2.9), ("dev", 3.2, 4.6), ("buddy", 4.9, 6.6), ("dev", 6.9, 7.8)]


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="scene/skit.blend")
    ap.add_argument("--timing", help="timing.json from `bh.py voices`; without it a short demo timeline")
    ap.add_argument("--horizontal", action="store_true", help="1920x1080 instead of 1080x1920")
    ap.add_argument("--samples", type=int, default=64)
    return ap.parse_args(argv)


# ---------- parts ----------

def part(kind, name, loc, mat, parent=None, scale=(1, 1, 1), rot=(0, 0, 0), bevel=0.0, **kw):
    """Add a primitive with its scale applied, flat-shaded, parented to `parent` at a local position."""
    add = {"cube": bpy.ops.mesh.primitive_cube_add, "cone": bpy.ops.mesh.primitive_cone_add,
           "cyl": bpy.ops.mesh.primitive_cylinder_add, "ico": bpy.ops.mesh.primitive_ico_sphere_add,
           "plane": bpy.ops.mesh.primitive_plane_add, "torus": bpy.ops.mesh.primitive_torus_add}[kind]
    if kind in ("cube", "plane"):
        kw.setdefault("size", 1)  # Blender's default is 2 units
    add(location=loc, rotation=[math.radians(r) for r in rot], **kw)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("Bevel", "BEVEL")
        mod.width, mod.segments, mod.limit_method = bevel, 1, "ANGLE"  # one chamfer keeps it low-poly
    obj.data.materials.append(mat)
    flat(obj)
    if parent:
        obj.parent = parent
    return obj


def empty(name, loc=(0, 0, 0), parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    obj.parent = parent
    return obj


def matte(name, color):
    """No shine at all: eyes and other ink marks stay black under strong lights."""
    mat = material(name, color, roughness=1.0)
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    spec = bsdf.inputs.get("Specular IOR Level") or bsdf.inputs.get("Specular")
    if spec:
        spec.default_value = 0.0
    return mat


def glow(name, color, strength):
    return material(name, (*color, 1), roughness=0.5, emission=(*color, 1, strength))


def make_laptop():
    deck = material("Deck", PARAMS["deck_color"], metallic=0.1, roughness=0.6)
    deck.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.15  # no glare at grazing angles
    keycap = material("Key", (0.008, 0.009, 0.014, 1), roughness=0.45)
    part("cube", "Laptop", (0, 0.6, -0.25), deck, scale=(17.5, 11.5, 0.5), bevel=0.15)
    part("cube", "Trackpad", (0, -4.0, 0.005), material("Trackpad", (0.03, 0.033, 0.045, 1), roughness=0.25),
         scale=(5.5, 2.2, 0.02))
    proto = part("cube", "Key", (0, 0, 0.07), keycap, scale=(0.95, 0.95, 0.14), bevel=0.05)
    rows, step = 5, 1.1
    for r in range(rows):
        y = -1.9 + r * step
        if r == 0:  # front row: a spacebar between short keys
            xs = [-6.05, -4.95, -3.85, 3.85, 4.95, 6.05]
            bar = part("cube", "Spacebar", (0, y, 0.07), keycap, scale=(6.5, 0.95, 0.14), bevel=0.05)
            bar.location.y = y
        else:
            xs = [(-6.5 + c) * step for c in range(14)]
        for x in xs:
            key = proto.copy()  # linked copies share one mesh
            key.location = (x, y, 0.07)
            bpy.context.scene.collection.objects.link(key)
    bpy.data.objects.remove(proto)


def make_screen(rnd):
    """Lid tilted back with a dark app UI drawn as glowing bars; it reads as an interface once out of focus."""
    lid = empty("Screen", (0, 6.6, 0))
    lid.rotation_euler = (math.radians(-14), 0, 0)
    part("cube", "Lid", (0, 0.2, 5.6), material("LidShell", PARAMS["deck_color"], metallic=0.3, roughness=0.35),
         parent=lid, scale=(17.4, 0.3, 11.2), bevel=0.15)
    part("plane", "Display", (0, 0.03, 5.6), glow("Display", (0.02, 0.022, 0.035), 0.6), parent=lid,
         scale=(16.4, 10.4, 1), rot=(90, 0, 0))
    text = glow("UIText", (0.75, 0.78, 0.9), 0.55)
    dim = glow("UIDim", (0.35, 0.38, 0.5), 0.35)
    accent = glow("UIAccent", PARAMS["warm"], 1.4)
    button = glow("UIButton", (0.25, 0.38, 1.0), 1.6)
    alert = glow("UIAlert", (0.9, 0.2, 0.18), 1.1)

    def bar(x, z, w, h, mat):
        part("cube", "UI", (x, 0, z), mat, parent=lid, scale=(w, 0.02, h))

    bar(0, 10.1, 15.6, 0.03, dim)  # title bar rule
    for i in range(5):  # sidebar
        bar(-6.6 + rnd.uniform(-0.1, 0.1), 9.2 - i * 0.6, rnd.uniform(1.2, 2.0), 0.16, dim)
    z = 9.3
    for i in range(8):  # message lines
        w = rnd.uniform(3.5, 9.5)
        bar(-3.6 + w / 2, z, w, 0.2, accent if i == 3 else text)
        z -= 0.62 if i % 3 != 2 else 0.95
    bar(-1.0, 2.1, 5.0, 0.55, alert)
    bar(3.4, 1.0, 3.0, 0.55, button)
    bar(0.6, 0.35, 12.5, 0.45, dim)  # prompt box
    return lid


def make_city(rnd):
    """A window that wraps around the set: navy sky, dark mullions, warm city lights that blur into bokeh.

    It surrounds the back and both sides, so close-ups that look past the screen still land on the city.
    """
    sky = part("cyl", "Sky", (0, 4, 12), glow("Sky", (0.012, 0.025, 0.11), 1.0), vertices=48, radius=48,
               depth=90, end_fill_type="NOTHING")
    sky.visible_shadow = False
    frame = material("Mullion", (0.004, 0.004, 0.008, 1), roughness=0.8)
    for deg in range(-20, 205, 22):
        a = math.radians(deg)
        part("cube", "Mullion", (34 * math.cos(a), 4 + 34 * math.sin(a), 12), frame, rot=(0, 0, deg),
             scale=(1.0, 1.0, 70))
    colors = [(1.0, 0.62, 0.3), (1.0, 0.8, 0.5), (1.0, 0.45, 0.2), (0.9, 0.9, 1.0)]
    mats = [glow(f"CityLight{i}", c, rnd.uniform(4, 9)) for i, c in enumerate(colors)]
    for _ in range(420):
        a, r = math.radians(rnd.uniform(-25, 205)), rnd.uniform(38, 44)
        part("ico", "CityLight", (r * math.cos(a), 4 + r * math.sin(a), rnd.triangular(-8, 30, 2)),
             rnd.choice(mats), scale=[rnd.uniform(0.14, 0.34)] * 3, subdivisions=1, radius=1)
    star = glow("Star", (0.85, 0.88, 1.0), 6)
    for _ in range(60):
        a = math.radians(rnd.uniform(-25, 205))
        part("ico", "Star", (45 * math.cos(a), 4 + 45 * math.sin(a), rnd.uniform(18, 40)), star, scale=[0.08] * 3,
             subdivisions=1, radius=1)


def make_buddy(at, facing_deg):
    root = empty("Buddy", (at[0], at[1], 0.14))
    root.rotation_euler.z = math.radians(facing_deg)
    body_mat = material("BuddyBody", PARAMS["buddy_color"], roughness=0.55)
    eye_mat = matte("BuddyEye", (0.003, 0.003, 0.005, 1))
    body = part("cube", "BuddyBody", (0, 0, 0.64), body_mat, parent=root, scale=(1.1, 0.85, 0.78), bevel=0.03)
    for x in (-0.6, 0.6):
        part("cube", "BuddyArm", (x * 1.02, -0.02, 0.56), body_mat, parent=root, scale=(0.2, 0.32, 0.22), bevel=0.02)
    for x in (-0.39, -0.13, 0.13, 0.39):
        part("cube", "BuddyLeg", (x, 0.02, 0.13), body_mat, parent=root, scale=(0.16, 0.16, 0.26), bevel=0.01)
    eyes = empty("BuddyEyes", (0, -0.43, 0.74), parent=root)
    for x in (-0.22, 0.22):
        part("cube", "BuddyEye", (x, 0, 0), eye_mat, parent=eyes, scale=(0.09, 0.03, 0.24))
    under = bpy.data.lights.new("BuddyGlow", "POINT")
    under.energy, under.color, under.shadow_soft_size = 25, PARAMS["warm"], 0.3
    lamp = bpy.data.objects.new("BuddyGlow", under)
    bpy.context.scene.collection.objects.link(lamp)
    lamp.parent, lamp.location = root, (0, -0.2, 0.12)
    return {"root": root, "focus": body, "eyes": eyes, "talk": "hop"}


def make_dev(at, facing_deg, rnd):
    root = empty("Dev", (at[0], at[1], 0.14))
    root.rotation_euler.z = math.radians(facing_deg)
    skin = material("Skin", PARAMS["skin_color"], roughness=0.65)
    hoodie = material("Hoodie", PARAMS["hoodie_color"], roughness=0.7)
    dark = material("Jeans", (0.01, 0.01, 0.022, 1), roughness=0.7)
    black = matte("Ink", (0.003, 0.003, 0.005, 1))
    hair = material("Hair", PARAMS["hair_color"], roughness=0.6)
    for x in (-0.17, 0.17):
        part("cube", "Shoe", (x, -0.06, 0.07), material("Shoe", (0.85, 0.85, 0.85, 1), roughness=0.6),
             parent=root, scale=(0.26, 0.44, 0.14), bevel=0.03)
        part("cyl", "Leg", (x, 0, 0.52), dark, parent=root, vertices=6, radius=0.12, depth=0.76)
    part("cone", "Torso", (0, 0, 1.3), hoodie, parent=root, vertices=8, radius1=0.44, radius2=0.33, depth=0.86)
    part("torus", "Hood", (0, 0.04, 1.74), hoodie, parent=root, major_segments=8, minor_segments=4,
         major_radius=0.27, minor_radius=0.1)
    for side in (-1, 1):
        part("cyl", "Arm", (side * 0.49, 0, 1.33), hoodie, parent=root, rot=(0, side * 9, 0),
             vertices=6, radius=0.1, depth=0.72)
        part("ico", "Hand", (side * 0.55, -0.02, 0.94), skin, parent=root, subdivisions=1, radius=0.1)
    part("cyl", "Neck", (0, 0, 1.8), skin, parent=root, vertices=6, radius=0.1, depth=0.16)
    head_pivot = empty("DevHead", (0, 0, 1.85), parent=root)
    head = part("ico", "Head", (0, 0, 0.3), skin, parent=head_pivot, scale=(0.92, 0.9, 1.1), subdivisions=2, radius=0.42)
    for v in head.data.vertices:  # taper toward the chin
        if v.co.z < 0:
            k = 1 + 0.55 * v.co.z  # z runs to about -0.46 at the chin
            v.co.x *= k
            v.co.y = v.co.y * k - 0.04 * (1 - k)
    facet(head, jitter=0.025, seed_value=3)
    for side in (-1, 1):
        part("ico", "Ear", (side * 0.41, 0.03, 0.28), skin, parent=head_pivot, subdivisions=1, radius=0.09)
        part("cube", "Brow", (side * 0.14, -0.35, 0.47), black, parent=head_pivot, rot=(0, side * -12, 0),
             scale=(0.15, 0.03, 0.03))
    eyes = empty("DevEyes", (0, -0.35, 0.36), parent=head_pivot)
    for side in (-1, 1):
        part("ico", "DevEye", (side * 0.14, 0, 0), black, parent=eyes, scale=(1, 0.6, 1.3), subdivisions=2, radius=0.05)
    part("cone", "Nose", (0, -0.4, 0.26), skin, parent=head_pivot, rot=(90, 0, 0), vertices=4, radius1=0.06, depth=0.12)
    mouth = part("cube", "Mouth", (0, -0.31, 0.12), black, parent=head_pivot, scale=(0.15, 0.05, 0.025))
    for i in range(22):  # spiky hair: cones along the normals of the top and back of the head
        theta = rnd.uniform(5, 70) if i < 16 else rnd.uniform(65, 100)
        phi = rnd.uniform(-60, 240) if i < 12 else rnd.uniform(0, 180)
        d = Vector((math.sin(math.radians(theta)) * math.cos(math.radians(phi)),
                    abs(math.sin(math.radians(theta)) * math.sin(math.radians(phi))) * 0.9 + 0.05,
                    math.cos(math.radians(theta))))
        d.normalize()
        base = Vector((0, 0.03, 0.33)) + d * 0.33
        spike = part("cone", "Hair", tuple(base + d * 0.12), hair, parent=head_pivot,
                     vertices=4, radius1=rnd.uniform(0.16, 0.24), depth=rnd.uniform(0.4, 0.68))
        spike.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    part("ico", "HairCap", (0, 0.12, 0.47), hair, parent=head_pivot, scale=(1.0, 0.95, 0.78), subdivisions=1, radius=0.44)
    return {"root": root, "focus": head, "eyes": eyes, "mouth": mouth, "head": head_pivot, "talk": "mouth"}


# ---------- animation ----------

def frame_of(t, fps):
    return 1 + round(t * fps)


def talk(char, start, end, fps, rnd):
    """Speaking: the buddy hops and squashes on each beat, the dev opens his mouth and nods."""
    f0, f1 = frame_of(start, fps), frame_of(end, fps)
    beat = max(3, round(fps * 0.12))
    if char["talk"] == "hop":
        root, z0 = char["root"], char["root"].location.z
        keyframe(root, f0 - 2, location=(*root.location[:2], z0), scale=(1, 1, 1))
        up = True
        for f in range(f0, f1, beat):
            h = rnd.uniform(0.03, 0.07) if up else 0.0
            keyframe(root, f, location=(*root.location[:2], z0 + h), scale=(1, 1, 1.04) if up else (1.02, 1.02, 0.97))
            up = not up
        keyframe(root, f1 + 2, location=(*root.location[:2], z0), scale=(1, 1, 1))
    else:
        mouth, head = char["mouth"], char["head"]
        keyframe(mouth, f0 - 2, scale=(1, 1, 1))
        keyframe(head, f0 - 2, rotation_euler=(0, 0, 0))
        for i, f in enumerate(range(f0, f1, beat)):
            keyframe(mouth, f, scale=(1, 1, rnd.uniform(2.5, 5.0) if i % 2 == 0 else 1.0))
            if i % 4 == 0:
                keyframe(head, f, rotation_euler=(math.radians(rnd.uniform(-5, 4)), 0, math.radians(rnd.uniform(-4, 4))))
        keyframe(mouth, f1 + 1, scale=(1, 1, 1))
        keyframe(head, f1 + 4, rotation_euler=(0, 0, 0))


def blinks(char, last_frame, fps, rnd):
    eyes, f = char["eyes"], round(fps * rnd.uniform(0.8, 2.0))
    while f < last_frame - 4:
        keyframe(eyes, f, scale=(1, 1, 1))
        keyframe(eyes, f + 2, scale=(1, 1, 0.1))
        keyframe(eyes, f + 4, scale=(1, 1, 1))
        f += round(fps * rnd.uniform(2.2, 4.2))


def drift(cam, target, frames, push=0.06, shake=0.004):
    """A slow push-in plus a little handheld sway, so held shots don't look frozen."""
    start = cam.location.copy()
    keyframe(cam, 1, location=start)
    keyframe(cam, frames, location=start.lerp(Vector(target), push))
    keyframe(cam, 1, rotation_euler=cam.rotation_euler.copy())
    for fc in fcurves(cam):
        fc.extrapolation = "LINEAR"
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
        if fc.data_path == "rotation_euler":
            noise = fc.modifiers.new("NOISE")
            noise.strength, noise.scale, noise.phase = shake, 45, fc.array_index * 13 + len(cam.name)


def build(a):
    reset()
    seed(7)
    rnd = random.Random(7)
    timing = json.loads(Path(a.timing).read_text(encoding="utf-8")) if a.timing else None
    lines = [(ln["speaker"], ln["start"], ln["end"]) for ln in timing["lines"]] if timing else DEMO
    seconds = timing["duration"] if timing else DEMO[-1][2] + 0.8
    w, h = PARAMS["size"]
    fps = PARAMS["fps"]
    scene = setup(*((h, w) if a.horizontal else (w, h)), fps=fps, seconds=seconds)
    scene.eevee.taa_render_samples = a.samples
    scene.render.use_motion_blur = True
    color_look("AgX", "Punchy", exposure=0.0)
    bloom(strength=0.55, threshold=0.6, size=0.7)

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.006, 0.022, 1)
    scene.world = world

    make_laptop()
    make_screen(rnd)
    make_city(rnd)
    dev = make_dev(PARAMS["dev_at"], 62, rnd)  # they face each other, turned a little toward the wide camera
    buddy = make_buddy(PARAMS["buddy_at"], -38)
    cast = {"dev": dev, "buddy": buddy}

    warm, cool = PARAMS["warm"], PARAMS["cool"]
    key = area_light((5.5, -3.5, 4.2), target=(0, 0.3, 1.2), power=1400, size=2.5, name="KeyWarm")
    key.data.color = warm
    front = area_light((-3.0, -4.5, 2.6), target=(*PARAMS["buddy_at"], 0.7), power=450, size=2, name="KeyWarmFront")
    front.data.color = warm
    rim = area_light((-4.5, 5.5, 6.0), target=(0, 0.3, 1.2), power=3000, size=6, name="RimCool")
    rim.data.color = cool
    fill = area_light((0, 6.0, 3.5), target=(0, 0, 1.0), power=350, size=10, name="ScreenFill")
    fill.data.color = (0.55, 0.6, 1.0)
    fill.data.specular_factor = 0.0  # light only; its reflection would wash out the deck in wide shots

    frames = scene.frame_end
    dx, dy = PARAMS["dev_at"]
    bx, by = PARAMS["buddy_at"]
    dev_head = (dx, dy, 2.3)
    buddy_body = (bx, by, 0.8)
    cams = {
        "dev": camera((dx + 3.0, dy - 1.6, 1.2), dev_head, lens=65, name="CamDev"),  # past the lid, onto the city
        "buddy": camera((bx - 2.3, by - 3.5, 0.6), buddy_body, lens=50, name="CamBuddy"),  # screen behind
        "wide": camera((0.6, -5.0, 1.45), (0, 0.6, 1.1), lens=28, name="CamWide"),
    }
    dof(cams["dev"], dev["focus"], fstop=1.2)
    dof(cams["buddy"], buddy["focus"], fstop=1.4)
    dof(cams["wide"], distance=(Vector((0, 0.6, 1.1)) - cams["wide"].location).length - 0.4, fstop=2.0)
    drift(cams["dev"], dev_head, frames)
    drift(cams["buddy"], buddy_body, frames)
    drift(cams["wide"], (0, 0.6, 1.1), frames, push=0.08)

    last_cut = -99
    for i, (speaker, start, end) in enumerate(lines):
        char = cast.get(speaker)
        if char:
            talk(char, start, end, fps, rnd)
        shot = "wide" if i == 0 or i % 5 == 4 or speaker not in cams else speaker
        f = 1 if i == 0 else frame_of(start, fps) - 2  # cut just before the line starts
        if f - last_cut >= fps * 0.5:
            cut_to(cams[shot], f)
            last_cut = f
    scene.camera = cams["wide"]
    for char in cast.values():
        blinks(char, frames, fps, rnd)
    for obj in (dev["root"], buddy["root"], dev["head"]):
        for fc in fcurves(obj):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
    look_at(key, (0, 0.3, 1.2))
    return scene


if __name__ == "__main__":
    a = args()
    build(a)
    print("saved", save(a.out))
