# Rig a static Meshy model with the Quaternius Universal Animation Library (CC0) skeleton and clips.
# Usage: python3.13 rig.py -- <meshy.glb> <UAL1.glb> <out.glb> <landmarks.json> [faces]
# landmarks.json: joint positions (Blender coords, Z up, feet at 0, model scaled to 1.829 tall, facing -Y)
import bpy, sys, json, math
from mathutils import Vector, Matrix, Quaternion
a = sys.argv[sys.argv.index("--") + 1:]
SRC, UAL, OUT, LM = a[:4]; FACES = int(a[4]) if len(a) > 4 else 8000
LJ = json.load(open(LM)); SPREAD = math.radians(LJ.pop("spread", 0))  # spread: degrees to hold the arms further out from the body (for wide creatures)
L = {k: Vector(v) for k, v in LJ.items()}
CLIPS = {"Walk_Loop": "walk", "Idle_Loop": "idle", "Celebration": "cheer", "Jog_Fwd_Loop": "run"}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=UAL)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
for o in [o for o in bpy.data.objects if o.type == "MESH"]: bpy.data.objects.remove(o)
orig = {b.name: b.matrix_local.copy() for b in arm.data.bones}

bpy.ops.import_scene.gltf(filepath=SRC, merge_vertices=True)
me = next(o for o in bpy.data.objects if o.type == "MESH")
bpy.ops.object.select_all(action="DESELECT"); me.select_set(True); bpy.context.view_layer.objects.active = me
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
zs = [v.co.z for v in me.data.vertices]; s = 1.829 / (max(zs) - min(zs)); z0 = min(zs)
for v in me.data.vertices: v.co = Vector((v.co.x * s, v.co.y * s, (v.co.z - z0) * s))
n0 = len(me.data.polygons)
d = me.modifiers.new("dec", "DECIMATE"); d.ratio = min(1, FACES / max(1, sum(len(p.vertices) - 2 for p in me.data.polygons)))
bpy.ops.object.modifier_apply(modifier="dec")
print("faces", n0, "->", len(me.data.polygons))

# 1) fit the skeleton to this body (A-pose arms as modelled)
def mir(p): return Vector((-p.x, p.y, p.z))
J = {}  # bone -> (head, tail)
J["pelvis"] = (L["hips"], L["spine1"]); J["spine_01"] = (L["spine1"], L["spine2"]); J["spine_02"] = (L["spine2"], L["spine3"])
J["spine_03"] = (L["spine3"], L["neck"]); J["neck_01"] = (L["neck"], L["head"]); J["Head"] = (L["head"], L["headtop"])
for sd, f in (("l", lambda p: p), ("r", mir)):
    J["clavicle_" + sd] = (f(L["clav"]), f(L["shoulder"])); J["upperarm_" + sd] = (f(L["shoulder"]), f(L["elbow"]))
    J["lowerarm_" + sd] = (f(L["elbow"]), f(L["wrist"])); J["hand_" + sd] = (f(L["wrist"]), f(L["wrist"]) + (f(L["fingertip"]) - f(L["wrist"])) * .3)
    J["thigh_" + sd] = (f(L["hip"]), f(L["knee"])); J["calf_" + sd] = (f(L["knee"]), f(L["ankle"]))
    J["foot_" + sd] = (f(L["ankle"]), f(L["ball"])); J["ball_" + sd] = (f(L["ball"]), f(L["toe"]))
bpy.ops.object.select_all(action="DESELECT"); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones
for b in eb: b.use_connect = False
old = {b.name: b.matrix.copy() for b in eb}; oldlen = {b.name: b.length for b in eb}
delta = {}
def place(name, h, t):
    b = eb[name]; M = old[name]; od = (M.to_quaternion() @ Vector((0, 1, 0)))
    q = od.rotation_difference((t - h).normalized()) @ M.to_quaternion()
    b.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4(); b.length = (t - h).length
    delta[name] = (M, b.matrix.copy(), (t - h).length / oldlen[name])
for n, (h, t) in J.items(): place(n, h, t)
def fit_rest(b):  # bones we did not place (fingers, leaves) ride along with their parent's change
    for c in b.children:
        if c.name not in J:
            pM, pN, k = delta[b.name]
            rel = pM.inverted() @ old[c.name]; rel.translation *= k
            c.matrix = pN @ rel; c.length = oldlen[c.name] * k; delta[c.name] = (old[c.name], c.matrix.copy(), k)
        fit_rest(c)
fit_rest(eb["root"]) if "root" in eb else None
eb["root"].head = Vector((0, 0, 0)); eb["root"].tail = Vector((0, 0, .3))
bpy.ops.object.mode_set(mode="OBJECT")

# 2) skin the body to it
bpy.ops.object.select_all(action="DESELECT"); me.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type="ARMATURE_AUTO")
unw = sum(1 for v in me.data.vertices if not any(g.weight > 0 for g in v.groups))
print("unweighted verts", unw, "of", len(me.data.vertices))

# 3) turn every bone back to the library's rest direction (T-pose), bake that into the body, make it the new rest
arm.animation_data_clear() if arm.animation_data else None
bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode="POSE")
def order(b):
    yield b
    for c in b.children: yield from order(c)
for b in order(arm.data.bones["root"] if "root" in arm.data.bones else arm.data.bones[0]):
    pb = arm.pose.bones[b.name]
    pb.matrix = Matrix.Translation(pb.matrix.translation) @ orig[b.name].to_quaternion().to_matrix().to_4x4()
    bpy.context.view_layer.update()
bpy.ops.object.mode_set(mode="OBJECT")
bpy.context.view_layer.objects.active = me
mod = next(m for m in me.modifiers if m.type == "ARMATURE"); bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode="POSE")
bpy.ops.pose.armature_apply(selected=False)
for pb in arm.pose.bones: pb.matrix_basis = Matrix()
bpy.ops.object.mode_set(mode="OBJECT")
m2 = me.modifiers.new("Armature", "ARMATURE"); m2.object = arm

# 4) keep only the clips the game uses, under the game's names
for act in list(bpy.data.actions):
    if act.name in CLIPS: act.name = CLIPS[act.name]; act.use_fake_user = True
    else: bpy.data.actions.remove(act)
if SPREAD:  # turn the upper arms outward in every key, relative to the shoulder, so the arms clear a wide body
    for sd, sg in (("l", -1), ("r", 1)):
        rr = arm.data.bones["upperarm_" + sd].matrix_local.to_quaternion()
        Q = rr.inverted() @ Quaternion((0, 1, 0), sg * SPREAD) @ rr
        path = 'pose.bones["upperarm_%s"].rotation_quaternion' % sd
        for act in bpy.data.actions:
            cb = act.layers[0].strips[0].channelbags[0] if hasattr(act, "layers") and act.layers else act  # Blender 4.4+ keeps curves in channel bags
            fc = [cb.fcurves.find(path, index=i) for i in range(4)]
            if not all(fc): continue
            for k in range(len(fc[0].keyframe_points)):
                q = Q @ Quaternion([c.keyframe_points[k].co[1] for c in fc])
                for i, c in enumerate(fc): c.keyframe_points[k].co[1] = q[i]; c.keyframe_points[k].handle_left[1] = c.keyframe_points[k].handle_right[1] = q[i]
if not arm.animation_data: arm.animation_data_create()
for act in bpy.data.actions:
    tr = arm.animation_data.nla_tracks.new(); tr.name = act.name; tr.strips.new(act.name, int(act.frame_range[0]), act)
arm.animation_data.action = None
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_animation_mode="NLA_TRACKS", export_image_format="JPEG", export_jpeg_quality=88, export_yup=True, export_def_bones=True, export_optimize_animation_size=True)
print("done", OUT)
