# Tiny Planet: badass player ship "Spiral Raptor".
# Run: Blender --background --python make_raptor.py -- <out_dir> [norender]
# Blender is Z-up with the nose toward -Y; the glTF export turns that into
# three.js Y-up with the nose toward +Z, which is what the game's ships use.
import bpy, bmesh, math, sys, os
from mathutils import Vector
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
import shipkit

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else os.getcwd()
RENDER = "norender" not in ARGS
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
root = bpy.data.objects.new("SpiralRaptor", None)
scene.collection.objects.link(root)


def lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def mat(name, color, metal=0.0, rough=0.5, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*lin(color), 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*lin(emit), 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


ARMOR = mat("Armor", "#565d6b", metal=0.75, rough=0.3)
PLATE = mat("Plate", "#7a8292", metal=0.7, rough=0.38)
BLACK = mat("Black", "#0d0f14", metal=0.6, rough=0.5)
RED = mat("Red", "#c4161c", metal=0.4, rough=0.35)
CANOPY = mat("Canopy", "#140608", metal=0.3, rough=0.04, emit="#ff4a10", strength=0.08)
NEON = mat("Neon", "#ff3b1f", emit="#ff3b1f", strength=12)
CORE = mat("EngineCore", "#ffd0a0", emit="#ff8a3a", strength=25)
BLUE = mat("Ion", "#6fe3ff", emit="#6fe3ff", strength=10)


def mesh_obj(name, bm, m, flat=True, bevel=0.0, loc=(0, 0, 0)):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = not flat
    o = bpy.data.objects.new(name, me)
    o.location = loc
    scene.collection.objects.link(o)
    o.parent = root
    me.materials.append(m)
    if bevel:
        b = o.modifiers.new("Bevel", "BEVEL")
        b.width = bevel
        b.segments = 2
        b.limit_method = "ANGLE"
        b.angle_limit = math.radians(30)
        b.harden_normals = False
    return o


def section(y, hw, zt, zb, cz=0.0, sx=0.0):
    """8-point armored cross-section: sharp top ridge, wide chined sides."""
    pts = [(0, zt), (hw * 0.55, zt * 0.8), (hw, 0.15 * zt), (hw * 0.7, -zb * 0.7),
           (0, -zb), (-hw * 0.7, -zb * 0.7), (-hw, 0.15 * zt), (-hw * 0.55, zt * 0.8)]
    return [(sx + x, y, cz + z) for x, z in pts]


def loft(name, secs, m, bevel=0.0, mirror_x=False):
    bm = bmesh.new()
    rings = [[bm.verts.new(p) for p in s] for s in secs]
    n = len(secs[0])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))
    return mesh_obj(name, bm, m, bevel=bevel)


def plate(name, outline, thick, m, z=0.0, tilt=0.0, bevel=0.003, loc=(0, 0, 0)):
    """Flat blade from (x, y) outline; tilt rolls it around the Y axis (anhedral)."""
    bm = bmesh.new()
    def pt(x, y, dz):
        r = math.radians(tilt)
        return (x * math.cos(r), y, z + x * math.sin(r) + dz)
    bot = [bm.verts.new(pt(x, y, -thick / 2)) for x, y in outline]
    top = [bm.verts.new(pt(x, y, thick / 2)) for x, y in outline]
    bm.faces.new(bot)
    bm.faces.new(top)
    for i in range(len(outline)):
        j = (i + 1) % len(outline)
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    return mesh_obj(name, bm, m, bevel=bevel, loc=loc)


def cyl(name, m, loc, r, depth, axis="Y", verts=24, scale=(1, 1, 1)):
    verts = 32 if verts in (8, 12) else verts
    rot = {"Y": (math.pi / 2, 0, 0), "Z": (0, 0, 0), "X": (0, math.pi / 2, 0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    o.data.materials.append(m)
    o.parent = root
    return o


def cone(name, m, loc, r1, r2, depth, verts=24):
    verts = 32 if verts in (8, 12) else verts
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=depth,
                                    location=loc, rotation=(math.pi / 2, 0, 0))
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(m)
    o.parent = root
    return o


def both(fn):
    for s, tag in ((1, "R"), (-1, "L")):
        fn(s, tag)


# ---- main hull: long armored wedge, nose at -Y
loft("Hull", [
    section(-0.34, 0.004, 0.003, 0.003, cz=-0.004),
    section(-0.26, 0.030, 0.020, 0.018, cz=-0.002),
    section(-0.14, 0.055, 0.040, 0.030),
    section(-0.02, 0.075, 0.052, 0.036),
    section(0.10, 0.085, 0.050, 0.040),
    section(0.20, 0.080, 0.042, 0.040),
    section(0.25, 0.070, 0.036, 0.036),
], ARMOR, bevel=0.0025)

# red war stripe on the nose spine
loft("NoseStripe", [
    section(-0.30, 0.003, 0.002, 0.001, cz=0.008),
    section(-0.24, 0.012, 0.004, 0.002, cz=0.019),
    section(-0.12, 0.020, 0.005, 0.002, cz=0.039),
], RED)

# angular canopy: dark glass with a hot inner glow
loft("Canopy", [
    section(-0.12, 0.004, 0.002, 0.002, cz=0.040),
    section(-0.07, 0.026, 0.020, 0.004, cz=0.045),
    section(0.00, 0.034, 0.030, 0.004, cz=0.050),
    section(0.05, 0.022, 0.018, 0.004, cz=0.052),
], CANOPY, bevel=0.0015)

# spine armor behind the canopy
loft("Spine", [
    section(0.04, 0.020, 0.012, 0.002, cz=0.050),
    section(0.14, 0.030, 0.020, 0.002, cz=0.048),
    section(0.24, 0.026, 0.012, 0.002, cz=0.040),
], PLATE, bevel=0.0015)


def side(s, tag):
    # chunky side intakes
    loft("Intake" + tag, [
        section(-0.06, 0.020, 0.022, 0.022, sx=s * 0.085, cz=-0.006),
        section(0.05, 0.030, 0.028, 0.028, sx=s * 0.095, cz=-0.006),
        section(0.22, 0.028, 0.026, 0.026, sx=s * 0.095, cz=-0.006),
    ], PLATE, bevel=0.002)
    cyl("IntakeMouth" + tag, BLACK, (s * 0.085, -0.062, -0.006), 0.018, 0.006, scale=(1, 1, 1.1))

    # main wings: aggressive swept blades with a slight anhedral
    wing = [(0.09, -0.06), (0.30, 0.10), (0.33, 0.17), (0.29, 0.19), (0.10, 0.17)]
    plate("Wing" + tag, [(s * x, y) for x, y in wing], 0.012, ARMOR, z=-0.012, tilt=-8 * s)
    # neon leading edge
    edge = [(0.092, -0.064), (0.302, 0.096), (0.306, 0.108), (0.096, -0.050)]
    plate("WingNeon" + tag, [(s * x, y) for x, y in edge], 0.007, NEON, z=-0.012, tilt=-8 * s, bevel=0)
    # red wingtip blades
    tip = [(0.29, 0.07), (0.335, 0.12), (0.34, 0.20), (0.30, 0.19)]
    plate("WingTip" + tag, [(s * x, y) for x, y in tip], 0.016, RED, z=-0.012, tilt=-8 * s)

    # forward canards
    can = [(0.05, -0.17), (0.13, -0.10), (0.13, -0.08), (0.05, -0.10)]
    plate("Canard" + tag, [(s * x, y) for x, y in can], 0.008, PLATE, z=0.004, tilt=6 * s)

    # canted twin tail fins
    bm = bmesh.new()
    lean = math.radians(22) * s
    def fp(y, h, dx):
        return (s * 0.06 + math.sin(lean) * h + dx, y, 0.02 + math.cos(lean) * h)
    a = [fp(0.10, 0, -0.005), fp(0.26, 0, -0.005), fp(0.27, 0.12, -0.005), fp(0.22, 0.12, -0.005)]
    b = [(x + 0.01, y, z) for x, y, z in a]
    va = [bm.verts.new(p) for p in a]
    vb = [bm.verts.new(p) for p in b]
    bm.faces.new(va)
    bm.faces.new(vb)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((va[i], va[j], vb[j], vb[i]))
    mesh_obj("TailFin" + tag, bm, ARMOR, bevel=0.002)
    # neon stripe on the fin
    bm = bmesh.new()
    a = [fp(0.215, 0.09, -0.0065), fp(0.265, 0.09, -0.0065), fp(0.268, 0.1, -0.0065), fp(0.218, 0.1, -0.0065)]
    b = [(x + 0.013, y, z) for x, y, z in a]
    va = [bm.verts.new(p) for p in a]
    vb = [bm.verts.new(p) for p in b]
    bm.faces.new(va)
    bm.faces.new(vb)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((va[i], va[j], vb[j], vb[i]))
    mesh_obj("FinNeon" + tag, bm, NEON)

    # heavy cannons slung under the wings
    x = s * 0.19
    cyl("CannonBody" + tag, BLACK, (x, 0.03, -0.03), 0.014, 0.16, verts=8)
    cyl("Barrel" + tag, PLATE, (x, -0.11, -0.03), 0.006, 0.14, verts=12)
    cyl("MuzzleBrake" + tag, BLACK, (x, -0.17, -0.03), 0.009, 0.02, verts=8)
    cyl("MuzzleGlow" + tag, NEON, (x, -0.181, -0.03), 0.004, 0.003, verts=12)
    cyl("Pylon" + tag, ARMOR, (x, 0.05, -0.02), 0.004, 0.08, verts=6, scale=(1, 1, 2.0))

    # engines: big armored nacelles with glowing exhausts
    ex = s * 0.055
    cyl("Nacelle" + tag, PLATE, (ex, 0.21, -0.004), 0.034, 0.12, verts=12)
    cone("Nozzle" + tag, BLACK, (ex, 0.285, -0.004), 0.030, 0.036, 0.04, verts=12)
    cyl("ExhaustRing" + tag, NEON, (ex, 0.305, -0.004), 0.030, 0.003, verts=24)
    cyl("ExhaustCore" + tag, CORE, (ex, 0.300, -0.004), 0.024, 0.004, verts=24)
    cyl("NacelleBand" + tag, RED, (ex, 0.17, -0.004), 0.0355, 0.012, verts=12)


both(side)

# center booster
cyl("CenterNozzle", BLACK, (0, 0.27, 0.02), 0.018, 0.04, verts=12)
cyl("CenterCore", BLUE, (0, 0.291, 0.02), 0.014, 0.004, verts=24)

# ---- small details: blinking wingtip and tail lights, a radio antenna
shipkit.nav_light(root, "NavL", (0.338, 0.165, -0.058), "#ff2a2a")   # Blender +X is the pilot's left
shipkit.nav_light(root, "NavR", (-0.338, 0.165, -0.058), "#2aff6a")
for s, tag in ((1, "L"), (-1, "R")):
    shipkit.nav_light(root, "Tail" + tag, (s * 0.108, 0.255, 0.134), "#ffffff", r=0.0045)
shipkit.antenna(root, BLACK, (0.0, 0.19, 0.06), 0.045)
shipkit.finish(root)
# ---- export
shipkit.export(os.path.join(OUT, "spiral_raptor.glb"))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "spiral_raptor.blend"))
if RENDER:
    shipkit.render(OUT, [("raptor_front.png", (0.75, -0.85, 0.5), (0, 0.02, -0.01)), ("raptor_back.png", (-0.7, 0.95, 0.45), (0, 0.02, -0.01))])
print("DONE", OUT)
