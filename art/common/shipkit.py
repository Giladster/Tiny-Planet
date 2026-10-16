# Tiny Planet: shared "high detail" pass for Blender ships.
# Import from a make_*.py script after building the ship, before export:
#   sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common")); import shipkit
#   shipkit.finish(root)
# It makes every part smooth and high quality:
#  - softly rounded edges (3-step bevels) and smooth shading with crisp creases
#  - panel lines, rivets, vents, dirt and scratches from the tiling hull textures
#    (art/common/textures, made by make_hull_textures.py)
# Glowing parts (materials with emission) stay plain so they glow cleanly.
import bpy, math, os

TEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")
_imgs = {}


def _img(name, color=True):
    if name not in _imgs:
        im = bpy.data.images.load(os.path.join(TEX, name), check_existing=True)
        im.colorspace_settings.name = "sRGB" if color else "Non-Color"
        _imgs[name] = im
    return _imgs[name]


def _glows(m):
    b = m.node_tree.nodes.get("Principled BSDF") if m and m.use_nodes else None
    return not b or b.inputs["Emission Strength"].default_value > 0.5


def detail_material(m, normal=1.0):
    """Hull textures on a material. Base color stays the factor, so the game can still tint it."""
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    if b.inputs["Base Color"].is_linked:
        return
    uv = nt.nodes.new("ShaderNodeUVMap")
    col = nt.nodes.new("ShaderNodeTexImage"); col.image = _img("hull_color.png")
    rgh = nt.nodes.new("ShaderNodeTexImage"); rgh.image = _img("hull_rough.png", False)
    nrm = nt.nodes.new("ShaderNodeTexImage"); nrm.image = _img("hull_normal.png", False)
    for t in (col, rgh, nrm):
        nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
    base = tuple(b.inputs["Base Color"].default_value)
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    nt.links.new(col.outputs["Color"], mix.inputs[6]); mix.inputs[7].default_value = base
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(rgh.outputs["Color"], sep.inputs["Color"])
    r = b.inputs["Roughness"].default_value
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = max(.05, r * 1.25)
    nt.links.new(sep.outputs["Green"], mul.inputs[0]); nt.links.new(mul.outputs[0], b.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = normal
    nt.links.new(nrm.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])


def finish(root, cube=0.24, bevel=0.0018, smooth_angle=34):
    objs = [o for o in bpy.data.objects if o.type == "MESH" and (o.parent == root or o == root)]
    done = set()
    for o in objs:
        m = o.data.materials[0] if o.data.materials else None
        glow = _glows(m)
        # rounded edges: every hard edge gets a soft 3-step bevel that catches the light
        bv = next((x for x in o.modifiers if x.type == "BEVEL"), None)
        if not bv and not glow:
            bv = o.modifiers.new("Bevel", "BEVEL"); bv.width = bevel; bv.limit_method = "ANGLE"; bv.angle_limit = math.radians(30)
        if bv:
            bv.segments = 3; bv.profile = .6; bv.use_clamp_overlap = True
        # smooth shading, but creases stay crisp
        for p in o.data.polygons:
            p.use_smooth = True
        wn = o.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL"); wn.keep_sharp = True
        try:
            o.data.set_sharp_from_angle(angle=math.radians(smooth_angle))
        except Exception:
            pass
        # UVs at the same size everywhere, so panels have the same scale on every part
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = o; o.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.cube_project(cube_size=cube / max(1e-6, max(o.scale)), correct_aspect=True, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        if m and not glow and m.name not in done:
            detail_material(m); done.add(m.name)
    bpy.ops.object.select_all(action="DESELECT")


def export(path):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_apply=True, export_yup=True,
                              export_image_format="JPEG", export_jpeg_quality=88)


def _glow_mat(name, hexcol, strength=14):
    m = bpy.data.materials.get(name)
    if m:
        return m
    h = hexcol.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*c, 1); b.inputs["Emission Color"].default_value = (*c, 1)
    b.inputs["Emission Strength"].default_value = strength
    return m


def nav_light(root, name, loc, hexcol, r=0.0055):
    """A small glowing bulb (red on the left, green on the right, white on the tail)."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=r, location=loc)
    o = bpy.context.active_object; o.name = name; o.parent = root
    o.data.materials.append(_glow_mat("Nav" + hexcol, hexcol))
    return o


def antenna(root, m, loc, h, r=0.0012):
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=r, depth=h, location=(loc[0], loc[1], loc[2] + h / 2))
    o = bpy.context.active_object; o.name = "Antenna"; o.parent = root; o.data.materials.append(m)
    return o


def render(out, shots, lens=40):
    """Preview pictures: shots = [(file, camera_pos, target)]."""
    from mathutils import Vector
    scene = bpy.context.scene
    world = bpy.data.worlds.new("Space"); world.use_nodes = True
    bg = world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.02, 0.018, 0.05, 1)
    scene.world = world
    for name, loc, energy, col in [("Key", (0.7, -0.3, 0.9), 110, (1, 0.93, 0.85)), ("Rim", (-0.7, 0.6, 0.4), 90, (1.0, 0.45, 0.3)),
                                   ("Top", (0, 0.1, 1.0), 60, (0.9, 0.9, 1)), ("Cool", (0.3, -0.9, -0.4), 40, (0.4, 0.7, 1))]:
        L = bpy.data.lights.new(name, "POINT"); L.energy = energy; L.color = col
        lo = bpy.data.objects.new(name, L); lo.location = loc; scene.collection.objects.link(lo)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); cam.data.lens = lens
    scene.collection.objects.link(cam); scene.camera = cam
    scene.render.engine = "CYCLES"  # works headless on any computer, no graphics card needed
    scene.cycles.device = "CPU"; scene.cycles.samples = 48; scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1100, 720
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Punchy"
    except Exception:
        pass
    for fname, pos, target in shots:
        cam.location = pos
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(out, fname)
        bpy.ops.render.render(write_still=True)
