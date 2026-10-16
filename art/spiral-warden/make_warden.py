# Tiny Planet: battle spaceship "Spiral Warden".
# Run: Blender --background --python make_warden.py -- <out_dir> [norender]
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
root = bpy.data.objects.new("SpiralWarden", None)
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


def box(y, hw, ht, hb, ch=0.3, cx=0.0, cz=0.0):
    """Chamfered box cross-section: flat armored sides with cut corners."""
    c = ch * min(hw, ht, hb)
    pts = [(hw - c, ht), (hw, ht - c), (hw, -hb + c), (hw - c, -hb), (-hw + c, -hb), (-hw, -hb + c), (-hw, ht - c), (-hw + c, ht)]
    return [(cx + x, y, cz + z) for x, z in pts]


def deck(name, outline, z, thick, m, scale=1.0, dy=0.0, bevel=0.003):
    return plate(name, [(x * scale, y * scale + dy) for x, y in outline], thick, m, z=z, bevel=bevel)


# ---- core hull: a heavy armored block, nose at -Y
loft("Core", [box(-0.12, 0.040, 0.025, 0.030), box(-0.02, 0.070, 0.040, 0.045),
              box(0.16, 0.078, 0.045, 0.050), box(0.25, 0.070, 0.040, 0.045)], ARMOR, bevel=0.002)

# twin forward prongs with a railgun between them
for s in (1, -1):
    loft("Prong" + ("R" if s > 0 else "L"), [
        box(0.00, 0.024, 0.030, 0.030, cx=s * 0.052),
        box(-0.18, 0.020, 0.024, 0.024, cx=s * 0.050),
        box(-0.30, 0.010, 0.012, 0.012, cx=s * 0.044),
        box(-0.35, 0.003, 0.004, 0.004, cx=s * 0.040),
    ], ARMOR, bevel=0.0015)
    # glowing inner rail
    plate("Rail" + ("R" if s > 0 else "L"), [(s * 0.027, -0.30), (s * 0.031, -0.30), (s * 0.033, -0.02), (s * 0.029, -0.02)], 0.012, NEON, z=0.0, bevel=0)
    # red armor caps on the prong tips
    loft("ProngCap" + ("R" if s > 0 else "L"), [
        box(-0.24, 0.0175, 0.0205, 0.0205, cx=s * 0.0475),
        box(-0.30, 0.0105, 0.0125, 0.0125, cx=s * 0.044),
        box(-0.352, 0.0035, 0.0045, 0.0045, cx=s * 0.040),
    ], RED)
cyl("Railgun", BLACK, (0, -0.16, 0), 0.011, 0.30, verts=8)
for i, y in enumerate((-0.26, -0.21, -0.16, -0.11)):
    cyl("Coil%d" % i, NEON, (0, y, 0), 0.0135, 0.006, verts=8)
cyl("RailMuzzle", BLUE, (0, -0.311, 0), 0.007, 0.003, verts=16)

# layered arrowhead armor deck, with a glowing seam underneath
DECK = [(0, -0.17), (0.13, 0.00), (0.16, 0.15), (0.11, 0.25), (-0.11, 0.25), (-0.16, 0.15), (-0.13, 0.00)]
deck("DeckGlow", DECK, 0.036, 0.004, NEON, scale=1.03, bevel=0)
deck("Deck", DECK, 0.046, 0.016, ARMOR)
deck("Deck2", DECK, 0.062, 0.014, PLATE, scale=0.62, dy=0.07)
for s in (1, -1):  # red warpaint chevrons on the front corners
    plate("Chevron" + ("R" if s > 0 else "L"), [(s * 0.02, -0.13), (s * 0.115, -0.005), (s * 0.095, 0.005), (s * 0.005, -0.11)], 0.004, RED, z=0.0555, bevel=0.001)

# reactor: a hot hexagonal core set into the upper deck
cyl("ReactorRing", BLACK, (0, 0.03, 0.072), 0.030, 0.010, axis="Z", verts=6)
cyl("Reactor", CORE, (0, 0.03, 0.074), 0.021, 0.010, axis="Z", verts=6)

# command bridge at the back with a glowing window slit
loft("Bridge", [box(0.12, 0.030, 0.020, 0.002, cz=0.090), box(0.15, 0.040, 0.030, 0.002, cz=0.090),
                box(0.22, 0.036, 0.024, 0.002, cz=0.090)], PLATE, bevel=0.0015)
plate("BridgeWindow", [(-0.026, 0.118), (0.026, 0.118), (0.034, 0.128), (-0.034, 0.128)], 0.006, NEON, z=0.113, bevel=0)
cyl("SensorMast", BLACK, (0.018, 0.2, 0.135), 0.002, 0.045, axis="Z", verts=6)
cyl("SensorMast2", BLACK, (-0.018, 0.205, 0.128), 0.002, 0.03, axis="Z", verts=6)
cyl("SensorTip", NEON, (0.018, 0.2, 0.158), 0.004, 0.004, axis="Z", verts=8)

# dorsal twin-gun turret in front of the reactor
loft("Turret", [box(-0.065, 0.020, 0.012, 0.002, cz=0.072), box(-0.03, 0.026, 0.014, 0.002, cz=0.072),
                box(-0.005, 0.022, 0.012, 0.002, cz=0.072)], PLATE, bevel=0.0015)
for s in (1, -1):
    cyl("TurretGun" + ("R" if s > 0 else "L"), BLACK, (s * 0.01, -0.10, 0.078), 0.0035, 0.08, verts=8)

# heavy weapon pods on armored struts
def pod(s, tag):
    x, z = s * 0.185, -0.025
    plate("Strut" + tag, [(s * 0.07, -0.02), (s * 0.17, -0.06), (s * 0.17, 0.16), (s * 0.07, 0.18)], 0.018, ARMOR, z=-0.008, tilt=-12 * s)
    plate("StrutGlow" + tag, [(s * 0.075, 0.172), (s * 0.165, 0.152), (s * 0.165, 0.158), (s * 0.075, 0.178)], 0.02, NEON, z=-0.008, tilt=-12 * s, bevel=0)
    loft("Pod" + tag, [box(-0.20, 0.016, 0.016, 0.016, cx=x, cz=z), box(-0.14, 0.028, 0.030, 0.030, cx=x, cz=z),
                       box(0.16, 0.030, 0.032, 0.032, cx=x, cz=z), box(0.22, 0.024, 0.026, 0.026, cx=x, cz=z)], PLATE, bevel=0.0015)
    loft("PodBand" + tag, [box(-0.06, 0.0305, 0.0325, 0.0325, cx=x, cz=z), box(-0.03, 0.0305, 0.0325, 0.0325, cx=x, cz=z)], RED)
    for dz in (0.013, -0.013):
        cyl("PodGun" + tag, BLACK, (x, -0.24, z + dz), 0.0055, 0.10, verts=8)
        cyl("PodMuzzle" + tag, NEON, (x, -0.291, z + dz), 0.0035, 0.003, verts=12)
    cyl("PodNozzle" + tag, BLACK, (x, 0.235, z), 0.02, 0.03, verts=6)
    cyl("PodFlame" + tag, CORE, (x, 0.251, z), 0.016, 0.003, verts=6)


both(pod)

# ventral keel blade
bm = bmesh.new()
a = [(-0.004, -0.02, -0.04), (-0.004, 0.22, -0.04), (-0.004, 0.23, -0.10), (-0.004, 0.16, -0.10)]
va = [bm.verts.new(p) for p in a]
vb = [bm.verts.new((0.004, y, z)) for _, y, z in a]
bm.faces.new(va); bm.faces.new(vb)
for i in range(4):
    j = (i + 1) % 4
    bm.faces.new((va[i], va[j], vb[j], vb[i]))
mesh_obj("Keel", bm, ARMOR, bevel=0.002)

# main engine block: four big thrusters
loft("EngineBlock", [box(0.22, 0.075, 0.042, 0.048), box(0.28, 0.08, 0.046, 0.05)], BLACK, bevel=0.002)
for ex in (-0.04, 0.04):
    for ez in (0.018, -0.022):
        cyl("Nozzle", PLATE, (ex, 0.29, ez), 0.021, 0.02, verts=8)
        cyl("Flame", CORE, (ex, 0.301, ez), 0.017, 0.003, verts=16)
        cyl("FlameRing", NEON, (ex, 0.30, ez), 0.0215, 0.002, verts=8)
# ---- small details: blinking corner lights and radio antennas on the bridge
shipkit.nav_light(root, "NavL", (0.163, 0.15, 0.056), "#ff2a2a")   # Blender +X is the pilot's left
shipkit.nav_light(root, "NavR", (-0.163, 0.15, 0.056), "#2aff6a")
for s, tag in ((1, "L"), (-1, "R")):
    shipkit.nav_light(root, "Pod" + tag + "Light", (s * 0.185, -0.205, 0.008), "#ffffff", r=0.0045)
shipkit.antenna(root, BLACK, (-0.03, 0.22, 0.112), 0.03)
shipkit.finish(root)
# ---- export
shipkit.export(os.path.join(OUT, "spiral_warden.glb"))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "spiral_warden.blend"))
if RENDER:
    shipkit.render(OUT, [("warden_front.png", (0.75, -0.85, 0.5), (0, 0.02, -0.01)), ("warden_back.png", (-0.7, 0.95, 0.45), (0, 0.02, -0.01))])
print("DONE", OUT)
