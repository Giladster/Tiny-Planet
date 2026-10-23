import bpy,sys
from mathutils import Vector
a=sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=a[0])
ms=[o for o in bpy.data.objects if o.type=="MESH"]
if len(a)>3:  # swap one texture: material name, new image file
    m=bpy.data.materials[a[2]]; n=next(n for n in m.node_tree.nodes if n.type=="TEX_IMAGE" and any(l.to_socket.name=="Base Color" for l in n.outputs[0].links))
    n.image=bpy.data.images.load(a[3]); print("swapped",a[2])
bpy.ops.object.select_all(action="DESELECT")
for o in ms: o.select_set(True)
bpy.context.view_layer.objects.active=ms[0]
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.join()
me=bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
for o in [o for o in bpy.data.objects if o.type!="MESH"]: bpy.data.objects.remove(o)
def mean(name):
    i=[k for k,m in enumerate(me.data.materials) if m.name==name][0]
    ps=[p.center for p in me.data.polygons if p.material_index==i]; return sum(ps,Vector())/len(ps)
print("buttons",mean("buttons"),"vents",mean("ventsmain_001"),"helmgold",mean("helm_gold"),"base",mean("base_002"))
bpy.ops.export_scene.gltf(filepath=a[1],export_format="GLB")
