"""Helpers for scene build scripts that run inside Blender.

    import sys; sys.path.insert(0, r"<skill>/scripts")
    from bh_scene import *

Every function works headless (blender -b) and through MCP for Blender's execute-code tool.
"""

import math
import random
from pathlib import Path

import bpy
from mathutils import Vector

__all__ = ["reset", "seed", "setup", "camera", "look_at", "hdri_world", "sun", "area_light",
           "material", "import_asset", "keyframe", "save", "fcurves", "dof", "cut_to", "bloom", "color_look",
           "facet", "flat"]


def reset(force=False):
    """Empty the scene and drop unused data, so a build script always starts clean.

    In a Blender window (for example through MCP for Blender) this would throw away the open file,
    so it only runs headless unless the user agreed and force=True.
    """
    if not bpy.app.background and not force:
        raise RuntimeError("reset() clears the open Blender file; run the build headless (bh.py build) "
                           "or pass force=True once the user agrees")
    bpy.ops.wm.read_factory_settings(use_empty=True)


def seed(n=7):
    random.seed(n)


def setup(width=1920, height=1080, fps=30, seconds=5.0, engine="eevee"):
    scene = bpy.context.scene
    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = width, height, 100
    r.fps, r.fps_base = fps, 1.0
    scene.frame_start, scene.frame_end = 1, max(1, round(seconds * fps))
    available = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    if engine == "cycles":
        r.engine = "CYCLES"
    else:
        r.engine = next(e for e in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") if e in available)
    return scene


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def camera(location=(7, -7, 4), target=(0, 0, 1), lens=50, name="Camera"):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    cam = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = location
    look_at(cam, target)
    bpy.context.scene.camera = cam
    return cam


def hdri_world(path, strength=1.0, rotation_deg=0.0):
    """Light the scene with an HDRI, e.g. one fetched by `bh.py polyhaven get`."""
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value[2] = math.radians(rotation_deg)
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(Path(path).resolve()), check_existing=True)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return world


def sun(strength=3.0, angle_deg=(50, 0, 35), name="Sun"):
    data = bpy.data.lights.new(name, "SUN")
    data.energy = strength
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_euler = [math.radians(a) for a in angle_deg]
    return obj


def area_light(location, target=(0, 0, 1), power=500, size=2.0, name="Area"):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.size = power, size
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)
    return obj


def material(name, color=(0.8, 0.8, 0.8, 1), metallic=0.0, roughness=0.5, transmission=0.0, emission=None):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    trans = bsdf.inputs.get("Transmission Weight") or bsdf.inputs.get("Transmission")
    if trans:
        trans.default_value = transmission
    if emission:
        bsdf.inputs["Emission Color"].default_value = emission[:4] if len(emission) >= 4 else (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = 1.0 if len(emission) < 5 else emission[4]
    return mat


def import_asset(path, collection_name=None):
    """Import .gltf/.glb/.fbx/.obj, or append every object from a .blend. Returns the new objects."""
    path = Path(path).resolve()
    before = set(bpy.data.objects)
    ext = path.suffix.lower()
    if ext in (".gltf", ".glb"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif ext == ".blend":
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.objects = list(src.objects)
        for obj in dst.objects:
            if obj is not None:
                bpy.context.scene.collection.objects.link(obj)
    else:
        raise ValueError(f"unsupported asset type: {ext}")
    new = [o for o in bpy.data.objects if o not in before]
    if collection_name:
        coll = bpy.data.collections.get(collection_name) or bpy.data.collections.new(collection_name)
        if coll.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(coll)
        for o in new:
            for c in o.users_collection:
                c.objects.unlink(o)
            coll.objects.link(o)
    return new


def keyframe(obj, frame, **props):
    """keyframe(cam, 1, location=(0,-8,2)); values are set, then keyed at that frame."""
    for prop, value in props.items():
        setattr(obj, prop, value)
        obj.keyframe_insert(data_path=prop, frame=frame)


def fcurves(obj):
    """All animation curves of an object, on any Blender version (4.4+ keeps them in layers/channelbags)."""
    action = obj.animation_data and obj.animation_data.action
    if not action:
        return []
    curves = list(getattr(action, "fcurves", []) or [])
    if not curves and hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    curves += list(bag.fcurves)
    return curves


def dof(cam, focus=None, fstop=2.0, distance=None):
    """Depth of field: focus on an object (it follows when the object moves) or at a distance."""
    d = cam.data.dof
    d.use_dof = True
    d.aperture_fstop = fstop
    if focus is not None:
        d.focus_object = focus
    elif distance is not None:
        d.focus_distance = distance
    return cam


def cut_to(cam, frame, name=None):
    """Hard cut: from `frame` on, the scene renders through `cam` (a timeline marker bound to the camera)."""
    marker = bpy.context.scene.timeline_markers.new(name or f"{cam.name}@{frame}", frame=frame)
    marker.camera = cam
    return marker


def bloom(strength=0.5, threshold=0.7, size=0.6):
    """Soft glow around bright areas, done in the compositor (EEVEE since 4.2 has no bloom switch).

    Blender 5.x keeps the compositor in a node group; 4.2-4.x uses scene.node_tree. Returns False if
    this version's glare node can't be set up, so the build still works without the glow.
    """
    scene = bpy.context.scene
    try:
        if hasattr(scene, "compositing_node_group"):
            nt = bpy.data.node_groups.new("Look", "CompositorNodeTree")
            nt.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            out = nt.nodes.new("NodeGroupOutput")
            scene.compositing_node_group = nt
        else:
            scene.use_nodes = True
            nt = scene.node_tree
            nt.nodes.clear()
            out = nt.nodes.new("CompositorNodeComposite")
        layers = nt.nodes.new("CompositorNodeRLayers")
        glare = nt.nodes.new("CompositorNodeGlare")
        if "Type" in glare.inputs:  # 4.5+: settings are sockets
            glare.inputs["Type"].default_value = "Bloom"
            glare.inputs["Threshold"].default_value = threshold
            glare.inputs["Strength"].default_value = strength
            glare.inputs["Size"].default_value = size
        else:
            glare.glare_type = "BLOOM" if "BLOOM" in [i.identifier for i in glare.bl_rna.properties["glare_type"].enum_items] else "FOG_GLOW"
            glare.threshold = threshold
            glare.mix = strength - 1.0  # -1 = image only, 0 = even mix
            glare.size = max(6, min(9, round(6 + size * 3)))
        nt.links.new(layers.outputs["Image"], glare.inputs["Image"])
        nt.links.new(glare.outputs["Image"], out.inputs[0])
        return True
    except (AttributeError, KeyError, TypeError, RuntimeError) as e:
        print(f"bloom: skipped ({e})")
        return False


def color_look(view="AgX", look="Punchy", exposure=0.0):
    """Tone mapping. Look names differ between versions ("AgX - Punchy" in 4.x), so both are tried."""
    vs = bpy.context.scene.view_settings
    try:
        vs.view_transform = view
    except TypeError:
        print(f"color_look: no view transform {view}")
        return
    for name in (look, f"{view} - {look}", "None"):
        try:
            vs.look = name
            break
        except TypeError:
            continue
    vs.exposure = exposure


def flat(obj):
    """Flat shading: every face reads as its own plane, the low-poly look."""
    for poly in obj.data.polygons:
        poly.use_smooth = False
    return obj


def facet(obj, jitter=0.03, seed_value=1):
    """Nudge every vertex a little, so flat-shaded primitives look hand-made rather than perfect."""
    rnd = random.Random(seed_value)
    for v in obj.data.vertices:
        v.co += Vector((rnd.uniform(-jitter, jitter), rnd.uniform(-jitter, jitter), rnd.uniform(-jitter, jitter)))
    return flat(obj)


def save(path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    return path
