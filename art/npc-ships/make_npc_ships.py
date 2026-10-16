# Tiny Planet: Blender models for the ships that fly around the galaxy.
#   krell_raider.glb   pirates (hull "shark")
#   star_hauler.glb    traders and freighters (hull "hauler")
#   police_cruiser.glb space police (hull "cruiser")
#   alien_saucer.glb   tourists and motherships (hull "saucer")
# Run: Blender --background --python make_npc_ships.py -- <out_dir> [norender]
# Blender is Z-up with the nose toward -Y; the glTF export turns that into three.js Y-up, nose +Z.
import bpy, bmesh, math, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
import shipkit

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else os.getcwd()
RENDER = "norender" not in ARGS
os.makedirs(OUT, exist_ok=True)
root = None


def lin(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def mat(name, color, metal=0.0, rough=0.5, emit=None, strength=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*lin(color), 1); b.inputs["Metallic"].default_value = metal; b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*lin(emit), 1); b.inputs["Emission Strength"].default_value = strength
    return m


def mesh_obj(name, bm, m, bevel=0.0, loc=(0, 0, 0)):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); o.location = loc
    bpy.context.scene.collection.objects.link(o); o.parent = root; me.materials.append(m)
    if bevel:
        b = o.modifiers.new("Bevel", "BEVEL"); b.width = bevel; b.segments = 3; b.limit_method = "ANGLE"; b.angle_limit = math.radians(30)
    return o


def ring(y, pts, sx=0.0, cz=0.0):
    return [(sx + x, y, cz + z) for x, z in pts]


def oct_(hw, zt, zb, ch=.35):  # chamfered 8-point section
    c = ch * min(hw, zt, zb)
    return [(hw - c, zt), (hw, zt - c), (hw, -zb + c), (hw - c, -zb), (-hw + c, -zb), (-hw, -zb + c), (-hw, zt - c), (-hw + c, zt)]


def loft(name, secs, m, bevel=0.0):
    bm = bmesh.new(); rings = [[bm.verts.new(p) for p in s] for s in secs]; n = len(secs[0])
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n; bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(rings[0]); bm.faces.new(list(reversed(rings[-1])))
    return mesh_obj(name, bm, m, bevel=bevel)


def plate(name, outline, thick, m, z=0.0, tilt=0.0, bevel=0.002):
    bm = bmesh.new(); r = math.radians(tilt)
    pt = lambda x, y, dz: (x * math.cos(r), y, z + x * math.sin(r) + dz)
    bot = [bm.verts.new(pt(x, y, -thick / 2)) for x, y in outline]; top = [bm.verts.new(pt(x, y, thick / 2)) for x, y in outline]
    bm.faces.new(bot); bm.faces.new(top)
    for i in range(len(outline)):
        j = (i + 1) % len(outline); bm.faces.new((bot[i], bot[j], top[j], top[i]))
    return mesh_obj(name, bm, m, bevel=bevel)


def cyl(name, m, loc, r, depth, axis="Y", verts=32, scale=(1, 1, 1)):
    rot = {"Y": (math.pi / 2, 0, 0), "Z": (0, 0, 0), "X": (0, math.pi / 2, 0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object; o.name = name; o.scale = scale; o.data.materials.append(m); o.parent = root
    return o


def sphere(name, m, loc, r, scale=(1, 1, 1), seg=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=r, location=loc)
    o = bpy.context.active_object; o.name = name; o.scale = scale; o.data.materials.append(m); o.parent = root
    return o


def torus(name, m, loc, R, r, axis="Z"):
    rot = {"Y": (math.pi / 2, 0, 0), "Z": (0, 0, 0)}[axis]
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=64, minor_segments=12, location=loc, rotation=rot)
    o = bpy.context.active_object; o.name = name; o.data.materials.append(m); o.parent = root
    return o


def engine(tag, M, x, y, z, r, core):
    cyl("Nacelle" + tag, M["Plate"], (x, y - 0.02, z), r * 1.15, 0.07)
    cyl("Nozzle" + tag, M["Black"], (x, y + 0.02, z), r, 0.025)
    cyl("Exhaust" + tag, core, (x, y + 0.033, z), r * .8, 0.004)


def new_ship(name):
    global root
    bpy.ops.wm.read_factory_settings(use_empty=True)
    root = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(root)
    return {
        "Hull": None, "Black": mat("Black", "#0d0f14", metal=0.6, rough=0.5),
        "Core": mat("EngineCore", "#ffd0a0", emit="#ff8a3a", strength=25),
    }


def finish(fname, shots_name):
    shipkit.finish(root)
    shipkit.export(os.path.join(OUT, fname + ".glb"))
    if RENDER:
        shipkit.render(OUT, [(shots_name + "_front.png", (0.75, -0.85, 0.5), (0, 0.02, -0.01))])


both = lambda fn: [fn(s, t) for s, t in ((1, "L"), (-1, "R"))]  # Blender +X is the pilot's left

# ================= Krell raider (pirate): a dark, spiky shark with glowing red eyes
M = new_ship("KrellRaider")
M["Hull"] = mat("Hull", "#2a1a1a", metal=0.55, rough=0.42); M["Trim"] = mat("Trim", "#601010", metal=0.4, rough=0.4)
M["Plate"] = mat("Plate", "#3a3436", metal=0.7, rough=0.35); M["Neon"] = mat("Neon", "#ff3030", emit="#ff3030", strength=14)
loft("Hull", [ring(-0.32, oct_(0.006, 0.004, 0.004)), ring(-0.22, oct_(0.05, 0.03, 0.03)), ring(-0.06, oct_(0.085, 0.055, 0.045)),
              ring(0.12, oct_(0.08, 0.05, 0.045)), ring(0.26, oct_(0.055, 0.035, 0.035))], M["Hull"], bevel=0.002)
loft("Jaw", [ring(-0.28, oct_(0.01, 0.004, 0.004), cz=-0.03), ring(-0.16, oct_(0.05, 0.012, 0.012), cz=-0.04), ring(0.0, oct_(0.06, 0.012, 0.012), cz=-0.045)], M["Trim"], bevel=0.0015)
for s, t in ((1, "L"), (-1, "R")):
    sphere("Eye" + t, M["Neon"], (s * 0.038, -0.19, 0.012), 0.009, scale=(1.6, 1, 0.6), seg=16)
    plate("Blade" + t, [(s * 0.07, -0.08), (s * 0.30, 0.02), (s * 0.31, 0.06), (s * 0.24, 0.07), (s * 0.075, 0.12)], 0.012, M["Plate"], z=-0.01, tilt=-10 * s)
    plate("BladeEdge" + t, [(s * 0.072, -0.083), (s * 0.30, 0.017), (s * 0.302, 0.027), (s * 0.075, -0.07)], 0.007, M["Neon"], z=-0.01, tilt=-10 * s, bevel=0)
    for i, y in enumerate((-0.02, 0.06, 0.14)):  # spikes along the back
        bm = bmesh.new(); h = 0.05 - i * 0.008
        vs = [bm.verts.new(p) for p in ((s * 0.03, y - 0.03, 0.04), (s * 0.03, y + 0.03, 0.04), (s * 0.055, y + 0.035, 0.04 + h))]
        vb = [bm.verts.new((x + s * 0.008, yy, z)) for x, yy, z in ((s * 0.03, y - 0.03, 0.04), (s * 0.03, y + 0.03, 0.04), (s * 0.055, y + 0.035, 0.04 + h))]
        bm.faces.new(vs); bm.faces.new(vb)
        for k in range(3):
            j = (k + 1) % 3; bm.faces.new((vs[k], vs[j], vb[j], vb[k]))
        mesh_obj("Spike%s%d" % (t, i), bm, M["Trim"], bevel=0.001)
    cyl("Gun" + t, M["Black"], (s * 0.13, -0.08, -0.025), 0.007, 0.16)
    engine(t, M, s * 0.045, 0.27, -0.002, 0.026, M["Core"])
shipkit.nav_light(root, "NavL", (0.31, 0.055, -0.065), "#ff2a2a"); shipkit.nav_light(root, "NavR", (-0.31, 0.055, -0.065), "#ff2a2a")
plate("Fin", [(-0.005, 0.08), (-0.005, 0.25), (-0.005, 0.27)], 0.0, M["Trim"])  # placeholder removed below
bpy.data.objects.remove(bpy.data.objects["Fin"])
bm = bmesh.new(); a = [(0, 0.10, 0.05), (0, 0.25, 0.04), (0, 0.29, 0.13), (0, 0.22, 0.12)]
va = [bm.verts.new((-0.005, y, z)) for _, y, z in a]; vb = [bm.verts.new((0.005, y, z)) for _, y, z in a]
bm.faces.new(va); bm.faces.new(vb)
for k in range(4):
    j = (k + 1) % 4; bm.faces.new((va[k], va[j], vb[j], vb[k]))
mesh_obj("TailFin", bm, M["Hull"], bevel=0.002)
finish("krell_raider", "raider")

# ================= Star hauler (trader): a cab up front, a spine of colorful cargo boxes, big engines
M = new_ship("StarHauler")
M["Hull"] = mat("Hull", "#8a8f99", metal=0.6, rough=0.4); M["Trim"] = mat("Trim", "#d8a040", metal=0.35, rough=0.45)
M["Plate"] = mat("Plate", "#5d636e", metal=0.7, rough=0.35); M["Neon"] = mat("Neon", "#ffd080", emit="#ffd080", strength=10)
glass = mat("Glass", "#10202a", metal=0.4, rough=0.05, emit="#5fc8ff", strength=0.6)
loft("Cab", [ring(-0.30, oct_(0.03, 0.02, 0.03)), ring(-0.24, oct_(0.07, 0.05, 0.05)), ring(-0.14, oct_(0.08, 0.06, 0.055))], M["Hull"], bevel=0.002)
loft("Windshield", [ring(-0.285, oct_(0.025, 0.012, 0.004), cz=0.02), ring(-0.235, oct_(0.06, 0.02, 0.004), cz=0.035)], glass, bevel=0.001)
cyl("Spine", M["Plate"], (0, 0.03, 0), 0.025, 0.36)
cols = [("CargoA", "#e07a2a"), ("CargoB", "#2a7ae0"), ("CargoC", "#e8e8e8"), ("CargoD", "#3aa860")]
for i, (nm, c) in enumerate(cols):
    cm = mat(nm, c, metal=0.3, rough=0.55); y = -0.09 + i * 0.075
    for s in (1, -1):
        loft(nm + ("L" if s > 0 else "R") + str(i), [ring(y, oct_(0.04, 0.035, 0.035, ch=.15), sx=s * 0.045), ring(y + 0.065, oct_(0.04, 0.035, 0.035, ch=.15), sx=s * 0.045)], cm, bevel=0.0015)
loft("EngineBlock", [ring(0.21, oct_(0.09, 0.05, 0.05)), ring(0.27, oct_(0.095, 0.055, 0.055))], M["Hull"], bevel=0.002)
plate("Stripe", [(-0.081, -0.20), (0.081, -0.20), (0.081, -0.185), (-0.081, -0.185)], 0.11, M["Trim"], z=0.0, bevel=0.001)
for t, x, z in (("L", 0.05, 0.022), ("R", -0.05, 0.022), ("C", 0.0, -0.025)):
    engine(t, M, x, 0.29, z, 0.026, M["Core"])
shipkit.antenna(root, M["Black"], (0.02, -0.17, 0.06), 0.05)
shipkit.nav_light(root, "NavL", (0.098, 0.25, 0.0), "#ff2a2a"); shipkit.nav_light(root, "NavR", (-0.098, 0.25, 0.0), "#2aff6a")
shipkit.nav_light(root, "Beacon", (0.02, -0.17, 0.112), "#ffb030")
finish("star_hauler", "hauler")

# ================= Police cruiser: white and blue, swept wings, a red and blue light bar
M = new_ship("PoliceCruiser")
M["Hull"] = mat("Hull", "#f2f5fb", metal=0.35, rough=0.3); M["Trim"] = mat("Trim", "#1f4fd7", metal=0.4, rough=0.35)
M["Plate"] = mat("Plate", "#9aa6bb", metal=0.7, rough=0.35); M["Neon"] = mat("Neon", "#4fa8ff", emit="#4fa8ff", strength=12)
glass = mat("Glass", "#0a1424", metal=0.4, rough=0.05, emit="#5fc8ff", strength=0.4)
loft("Hull", [ring(-0.30, oct_(0.01, 0.006, 0.006)), ring(-0.20, oct_(0.05, 0.035, 0.03)), ring(-0.04, oct_(0.07, 0.05, 0.04)),
              ring(0.14, oct_(0.07, 0.045, 0.04)), ring(0.25, oct_(0.05, 0.03, 0.03))], M["Hull"], bevel=0.002)
loft("Canopy", [ring(-0.17, oct_(0.01, 0.004, 0.003), cz=0.03), ring(-0.10, oct_(0.035, 0.022, 0.003), cz=0.04), ring(-0.02, oct_(0.035, 0.02, 0.003), cz=0.045)], glass, bevel=0.001)
loft("Stripe", [ring(-0.20, oct_(0.051, 0.012, 0.012)), ring(0.25, oct_(0.051, 0.012, 0.012))], M["Trim"])
loft("LightBar", [ring(0.0, oct_(0.04, 0.006, 0.002), cz=0.05), ring(0.03, oct_(0.04, 0.006, 0.002), cz=0.05)], M["Black"], bevel=0.001)
red = mat("SirenRed", "#ff2030", emit="#ff2030", strength=18); blue = mat("SirenBlue", "#2050ff", emit="#2050ff", strength=18)
cyl("SirenL", red, (0.022, 0.015, 0.059), 0.009, 0.012, axis="Z", verts=24)
cyl("SirenR", blue, (-0.022, 0.015, 0.059), 0.009, 0.012, axis="Z", verts=24)
for s, t in ((1, "L"), (-1, "R")):
    plate("Wing" + t, [(s * 0.06, -0.02), (s * 0.24, 0.12), (s * 0.25, 0.17), (s * 0.06, 0.15)], 0.012, M["Hull"], z=-0.012, tilt=-6 * s)
    plate("WingTrim" + t, [(s * 0.20, 0.09), (s * 0.24, 0.12), (s * 0.25, 0.17), (s * 0.21, 0.165)], 0.014, M["Trim"], z=-0.012, tilt=-6 * s)
    plate("WingNeon" + t, [(s * 0.062, -0.024), (s * 0.24, 0.115), (s * 0.24, 0.125), (s * 0.062, -0.012)], 0.007, M["Neon"], z=-0.012, tilt=-6 * s, bevel=0)
    engine(t, M, s * 0.04, 0.27, 0.0, 0.024, M["Neon"])
shipkit.nav_light(root, "NavL", (0.252, 0.165, -0.04), "#ff2a2a"); shipkit.nav_light(root, "NavR", (-0.252, 0.165, -0.04), "#2aff6a")
finish("police_cruiser", "police")

# ================= Alien saucer: a shiny disk with a glass dome, a ring of lights and a glowing belly
M = new_ship("AlienSaucer")
M["Hull"] = mat("Hull", "#ff9ad5", metal=0.6, rough=0.25); M["Trim"] = mat("Trim", "#ffffff", metal=0.7, rough=0.2)
M["Plate"] = mat("Plate", "#b0b4c0", metal=0.8, rough=0.3); M["Neon"] = mat("Neon", "#ffe36a", emit="#ffe36a", strength=12)
dome = mat("Dome", "#9ff0ff", metal=0.2, rough=0.03, emit="#7ae8ff", strength=0.8)
sphere("Disk", M["Hull"], (0, 0, 0), 0.22, scale=(1, 1, 0.2), seg=64)
torus("Rim", M["Trim"], (0, 0, 0), 0.215, 0.018)
sphere("Belly", M["Plate"], (0, 0, -0.02), 0.13, scale=(1, 1, 0.35), seg=48)
cyl("BellyGlow", M["Neon"], (0, 0, -0.065), 0.06, 0.006, axis="Z", verts=48)
sphere("Dome", dome, (0, 0, 0.03), 0.09, scale=(1, 1, 0.7), seg=48)
torus("DomeRing", M["Trim"], (0, 0, 0.032), 0.09, 0.008)
for i in range(12):
    a = i / 12 * math.tau
    shipkit.nav_light(root, "Rim%d" % i, (math.cos(a) * 0.236, math.sin(a) * 0.236, 0.0), "#ffe36a", r=0.009)
for i in range(3):  # little thrusters at the back
    a = math.pi / 2 + (i - 1) * 0.5
    cyl("Thruster%d" % i, M["Black"], (math.cos(a) * 0.17, math.sin(a) * 0.17, -0.03), 0.018, 0.03)
finish("alien_saucer", "saucer")
print("DONE", OUT)
