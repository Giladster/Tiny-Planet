# Tiny Planet: test player ship "Spiral Scout".
# Run: Blender --background --python make_ship.py -- <out_dir>
# Blender is Z-up with the nose toward -Y; the glTF export turns that into
# three.js Y-up with the nose toward +Z, which is what the game's ships use.
import bpy, bmesh, math, sys, os
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.getcwd()
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def mat(name, color, metal=0.0, rough=0.5, emit=None, strength=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        m.blend_method = "BLEND"
    return m


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


BODY = mat("Body", srgb("#f2f4fb"), metal=0.35, rough=0.3)
ACCENT = mat("Accent", srgb("#ff5a8a"), metal=0.2, rough=0.35)
TRIM = mat("Trim", srgb("#ffb547"), metal=0.5, rough=0.3)
DARK = mat("Dark", srgb("#1c2030"), metal=0.7, rough=0.35)
GLASS = mat("Glass", srgb("#6fe3ff"), metal=0.1, rough=0.05, emit=srgb("#2aa8d8"), strength=0.6)
GLOW = mat("Glow", srgb("#7dfff0"), emit=srgb("#7dfff0"), strength=6)


def finish(obj, m, smooth=True, sub=0):
    obj.data.materials.append(m)
    if sub:
        mod = obj.modifiers.new("Sub", "SUBSURF")
        mod.levels = mod.render_levels = sub
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
    return obj


def lathe(name, length, radius, profile, m, loc=(0, 0, 0), sx=1.0, sz=1.0, segs=32, rings=28):
    """Smooth body turned around the Y axis, nose at -Y."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    verts = []
    for i in range(rings + 1):
        t = i / rings
        r = max(0.0008, radius * profile(t))
        y = (0.5 - t) * length  # t=1 is the nose (-Y)
        ring = [bm.verts.new((math.cos(a) * r * sx, y, math.sin(a) * r * sz))
                for a in (2 * math.pi * k / segs for k in range(segs))]
        verts.append(ring)
    for i in range(rings):
        for k in range(segs):
            a, b = verts[i][k], verts[i][(k + 1) % segs]
            c, d = verts[i + 1][(k + 1) % segs], verts[i + 1][k]
            bm.faces.new((a, b, c, d))
    bm.faces.new(list(reversed(verts[0])))
    bm.faces.new(verts[-1])
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.location = loc
    scene.collection.objects.link(obj)
    return finish(obj, m)


def slab(name, pts, depth, m, loc=(0, 0, 0), bevel=0.006):
    """Flat bevelled plate from a 2D outline (x = side, y = forward toward nose)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bot = [bm.verts.new((x, -y, -depth / 2)) for x, y in pts]
    top = [bm.verts.new((x, -y, depth / 2)) for x, y in pts]
    n = len(pts)
    bm.faces.new(bot)
    bm.faces.new(list(reversed(top)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.location = loc
    scene.collection.objects.link(obj)
    for f in me.polygons:
        f.use_smooth = False
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = bevel
    mod.segments = 3
    if me.polygons[0].normal.z > 0:  # keep outward normals
        bpy.context.view_layer.objects.active = obj
    obj.data.materials.append(m)
    return obj


def prim(kind, name, m, loc, scale=(1, 1, 1), rot=(0, 0, 0), **kw):
    getattr(bpy.ops.mesh, "primitive_%s_add" % kind)(location=loc, rotation=rot, **kw)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    return finish(o, m)


# ---- body: rounded, a bit flat, pointy nose
nose = lambda t: (0.75 + 0.25 * math.sin(t / 0.65 * math.pi / 2)) if t < 0.65 else max(0, math.cos((t - 0.65) / 0.35 * math.pi / 2)) ** 0.7
tail = lambda t: nose(t) * (0.82 + 0.18 * min(1, t / 0.25))
lathe("Hull", 0.56, 0.07, tail, BODY, sz=0.78)
# pink stripe along the top
lathe("Stripe", 0.40, 0.0715, lambda t: math.sin(math.pi * t) ** 0.35 * 0.98, ACCENT, loc=(0, -0.04, 0.003), sx=0.32, sz=0.8)

# ---- canopy
prim("uv_sphere", "Canopy", GLASS, (0, -0.07, 0.04), (0.04, 0.11, 0.032), segments=32, ring_count=16)
prim("torus", "CanopyRim", TRIM, (0, -0.07, 0.04), (0.042, 0.112, 0.6), major_radius=1, minor_radius=0.05, major_segments=48, minor_segments=8)

# ---- swept wings with orange tips
wing = [(0.05, 0.06), (0.24, -0.08), (0.27, -0.13), (0.25, -0.16), (0.05, -0.14)]
for s in (-1, 1):
    pts = [(s * x, y) for x, y in wing]
    if s < 0:
        pts.reverse()
    slab("Wing" + ("L" if s < 0 else "R"), pts, 0.014, BODY, loc=(0, 0, -0.012))
    tip = [(s * x, y) for x, y in [(0.225, -0.05), (0.27, -0.13), (0.25, -0.16), (0.215, -0.15)]]
    if s < 0:
        tip.reverse()
    slab("WingTip" + ("L" if s < 0 else "R"), tip, 0.018, ACCENT, loc=(0, 0, -0.012))
    # little nav light on each wing tip
    prim("uv_sphere", "NavLight" + ("L" if s < 0 else "R"), GLOW, (s * 0.262, 0.145, -0.012), (0.009,) * 3, segments=12, ring_count=8)

# ---- engine pods with glowing nozzles
pod = lambda t: math.sin(math.pi * (0.12 + t * 0.8)) ** 0.5
for s in (-1, 1):
    x = s * 0.095
    lathe("Pod" + ("L" if s < 0 else "R"), 0.22, 0.034, pod, TRIM, loc=(x, 0.13, -0.008))
    prim("cylinder", "Nozzle" + ("L" if s < 0 else "R"), DARK, (x, 0.24, -0.008), (0.026, 0.026, 0.02), rot=(math.pi / 2, 0, 0), vertices=24)
    prim("cylinder", "Flame" + ("L" if s < 0 else "R"), GLOW, (x, 0.262, -0.008), (0.02, 0.02, 0.004), rot=(math.pi / 2, 0, 0), vertices=24)

# ---- tail fin and antenna (for Bolt's radio)
fin = bpy.data.meshes.new("TailFin")
bm = bmesh.new()
outline = [(0.11, 0.0), (0.27, 0.0), (0.27, 0.1), (0.22, 0.1)]  # (y back, z up)
a = [bm.verts.new((-0.006, y, z)) for y, z in outline]
b = [bm.verts.new((0.006, y, z)) for y, z in outline]
bm.faces.new(a)
bm.faces.new(list(reversed(b)))
for i in range(4):
    j = (i + 1) % 4
    bm.faces.new((a[i], b[i], b[j], a[j]))
bm.normal_update()
bm.to_mesh(fin)
bm.free()
fo = bpy.data.objects.new("TailFin", fin)
fo.location = (0, 0, 0.03)
scene.collection.objects.link(fo)
fo.modifiers.new("Bevel", "BEVEL").width = 0.004
fo.data.materials.append(ACCENT)
prim("cylinder", "Antenna", DARK, (0, 0.235, 0.16), (0.003, 0.003, 0.03), vertices=8)
prim("uv_sphere", "AntennaTip", GLOW, (0, 0.235, 0.192), (0.008,) * 3, segments=12, ring_count=8)

# fix normals on all meshes
for o in scene.objects:
    if o.type == "MESH":
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")

# ---- parent everything to one root so the game gets a single object
root = bpy.data.objects.new("SpiralScout", None)
scene.collection.objects.link(root)
for o in list(scene.objects):
    if o is not root and o.type == "MESH":
        o.parent = root

bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "spiral_scout.glb"), export_format="GLB",
                          export_apply=True, export_yup=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "spiral_scout.blend"))

# ---- preview renders
world = bpy.data.worlds.new("Space")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.012, 0.01, 0.035, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
scene.world = world
for name, loc, energy, col in [("Key", (0.6, 0.4, 0.8), 60, (1, 0.95, 0.9)),
                               ("Rim", (-0.6, -0.5, 0.3), 40, (0.6, 0.5, 1)),
                               ("Fill", (0.2, -0.8, -0.3), 15, (0.5, 0.9, 1))]:
    L = bpy.data.lights.new(name, "POINT")
    L.energy = energy
    L.color = col
    lo = bpy.data.objects.new(name, L)
    lo.location = loc
    scene.collection.objects.link(lo)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.data.lens = 50
scene.collection.objects.link(cam)
scene.camera = cam
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.eevee.taa_render_samples = 32
scene.render.resolution_x, scene.render.resolution_y = 1000, 700
scene.view_settings.view_transform = "AgX"
try:
    scene.eevee.use_bloom = True
except Exception:
    pass


def shoot(fname, pos):
    cam.location = pos
    d = Vector((0, 0.02, 0)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, fname)
    bpy.ops.render.render(write_still=True)


shoot("preview_front.png", (0.55, -0.6, 0.35))
shoot("preview_back.png", (-0.5, 0.65, 0.3))
print("DONE", OUT)
