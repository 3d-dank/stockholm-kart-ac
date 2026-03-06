"""
Stockholm Karting Center — Step 2: Build from Traced Curve
==========================================================
Run this AFTER you've traced the track in trace_setup.py and are
happy with the shape.

How to run:
  1. With your traced "track_centerline" curve object in the scene
  2. Go to Scripting workspace
  3. Open this file and press Run Script (▶)
  4. Exports FBX to content/tracks/stockholm_karting/models/

OR run from command line (after saving the .blend file with your curve):
  blender.exe yourfile.blend --python build_from_curve.py
"""

import bpy
import math
import os

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "content", "tracks", "stockholm_karting", "models")
TRACK_WIDTH = 7.92   # 26 ft

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── FIND CURVE OBJECT ─────────────────────────────────────────────────────────
curve_obj = bpy.data.objects.get("track_centerline")
if curve_obj is None:
    # Try active object
    curve_obj = bpy.context.active_object
    if curve_obj is None or curve_obj.type != 'CURVE':
        raise RuntimeError("No 'track_centerline' curve found. Run trace_setup.py first and trace the track.")

print(f"[Build] Using curve: {curve_obj.name}")

# ── EVALUATE CURVE → CENTERLINE POINTS ───────────────────────────────────────
dep     = bpy.context.evaluated_depsgraph_get()
ev_obj  = curve_obj.evaluated_get(dep)
ev_mesh = ev_obj.to_mesh()
center  = [(v.co.x, v.co.y) for v in ev_mesh.vertices]
ev_obj.to_mesh_clear()

if len(center) < 10:
    raise RuntimeError(f"Curve only gave {len(center)} points — check your curve has enough resolution.")

N = len(center)
print(f"[Build] Centerline: {N} evaluated points")

total_m = sum(
    math.hypot(center[(i+1)%N][0]-center[i][0], center[(i+1)%N][1]-center[i][1])
    for i in range(N-1)
)
print(f"[Build] Approx length: {total_m:.0f}m (target ~1047m)")

# ── MATERIALS ─────────────────────────────────────────────────────────────────
def mat(name, r, g, b, rough=0.85):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
        bsdf.inputs["Roughness"].default_value = rough
    return m

MAT_ASPHALT = mat("road_asphalt",  0.08, 0.08, 0.08)
MAT_PIT     = mat("pit_asphalt",   0.14, 0.14, 0.14)
MAT_GRASS   = mat("terrain_grass", 0.20, 0.45, 0.15)
MAT_KERB_R  = mat("kerb_red",      0.82, 0.08, 0.08, 0.6)
MAT_KERB_W  = mat("kerb_white",    0.90, 0.90, 0.90, 0.6)
MAT_BARRIER = mat("barrier",       0.50, 0.50, 0.50)
MAT_LINE    = mat("start_line",    0.95, 0.95, 0.95, 0.4)

# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────
def normal_at(pts, i):
    n = len(pts)
    ax, ay = pts[(i-1)%n]
    bx, by = pts[(i+1)%n]
    dx, dy = bx-ax, by-ay
    L = math.hypot(dx, dy) or 1
    return -dy/L, dx/L

def build_strip(pts, width, z=0.0, name="surface", closed=False):
    hw = width / 2
    verts, faces = [], []
    n = len(pts)
    rng = n if closed else n - 1
    for i in range(n):
        nx, ny = normal_at(pts, i)
        cx, cy = pts[i]
        verts.append((cx - nx*hw, cy - ny*hw, z))
        verts.append((cx + nx*hw, cy + ny*hw, z))
    for i in range(rng):
        a, b = i*2, i*2+1
        c, d = ((i+1)%n)*2, ((i+1)%n)*2+1
        faces.append((a, b, d, c))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob

def corner_radius(pts, i):
    n = len(pts)
    ax,ay = pts[(i-1)%n]; bx,by = pts[i]; cx,cy = pts[(i+1)%n]
    v1x,v1y = bx-ax, by-ay
    v2x,v2y = cx-bx, cy-by
    cross = abs(v1x*v2y - v1y*v2x)
    l1 = math.hypot(v1x, v1y); l2 = math.hypot(v2x, v2y)
    if cross < 0.01 or l1 < 0.01 or l2 < 0.01: return 9999
    sin_a = min(cross / (l1*l2), 1.0)
    angle = math.asin(sin_a)
    if angle < 0.01: return 9999
    return min(l1, l2) / (2 * math.tan(angle/2 + 0.001))

# ── REMOVE OLD MESH OBJECTS (keep curve + satellite) ──────────────────────────
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name not in ("satellite_background",):
        bpy.data.objects.remove(o, do_unlink=True)

# ── TRACK SURFACE ─────────────────────────────────────────────────────────────
print("[Build] Building track surface…")
track_obj = build_strip(center, TRACK_WIDTH, z=0.0, name="track_surface")
track_obj.data.materials.append(MAT_ASPHALT)

# ── START LINE ────────────────────────────────────────────────────────────────
sfx, sfy = center[0]
nx, ny   = normal_at(center, 0)
tx = center[1][0]-center[0][0]; ty = center[1][1]-center[0][1]
tl = math.hypot(tx,ty) or 1; tx/=tl; ty/=tl
hw = TRACK_WIDTH/2; lw = 0.5
sv = [(sfx-nx*hw-tx*lw, sfy-ny*hw-ty*lw, 0.01),
      (sfx+nx*hw-tx*lw, sfy+ny*hw-ty*lw, 0.01),
      (sfx+nx*hw+tx*lw, sfy+ny*hw+ty*lw, 0.01),
      (sfx-nx*hw+tx*lw, sfy-ny*hw+ty*lw, 0.01)]
sme = bpy.data.meshes.new("start_line")
sme.from_pydata(sv, [], [(0,1,2,3)]); sme.update()
sobj = bpy.data.objects.new("start_line", sme)
bpy.context.scene.collection.objects.link(sobj)
sobj.data.materials.append(MAT_LINE)

# ── TERRAIN ───────────────────────────────────────────────────────────────────
# Find track bounds to center terrain
xs = [p[0] for p in center]; ys = [p[1] for p in center]
tc_x = (min(xs)+max(xs))/2; tc_y = (min(ys)+max(ys))/2
bpy.ops.mesh.primitive_plane_add(size=800, location=(tc_x, tc_y, -0.05))
terrain = bpy.context.active_object
terrain.name = "terrain"
terrain.data.materials.append(MAT_GRASS)
print(f"  Track bounds: X {min(xs):.0f}–{max(xs):.0f}, Y {min(ys):.0f}–{max(ys):.0f}")

# ── KERBS ─────────────────────────────────────────────────────────────────────
print("[Build] Building kerbs…")
KERB_W = 0.35; KERB_H_T = 0.04; KERB_H_S = 0.01; KERB_SL = 1.2
hw = TRACK_WIDTH/2
kerb_count = 0; seg_idx = 0; skip = 0

for i in range(1, N-1):
    if skip > 0: skip -= 1; continue
    r = corner_radius(center, i)
    if r > 35: continue
    skip = 3
    h = KERB_H_T if r < 15 else KERB_H_S
    cx,cy = center[i]; nrx,nry = normal_at(center,i)
    tx2 = center[min(i+1,N-1)][0]-center[i][0]
    ty2 = center[min(i+1,N-1)][1]-center[i][1]
    tl2 = math.hypot(tx2,ty2) or 1; tx2/=tl2; ty2/=tl2
    for side, mats in [(-1,[MAT_KERB_R,MAT_KERB_W]),(1,[MAT_KERB_W,MAT_KERB_R])]:
        mk = mats[seg_idx%2]
        ox = cx+side*(hw+KERB_W*0.5)*nrx; oy = cy+side*(hw+KERB_W*0.5)*nry
        sl = KERB_SL*0.5
        kv = [(ox-tx2*sl-nrx*KERB_W*0.5, oy-ty2*sl-nry*KERB_W*0.5, 0),
              (ox-tx2*sl+nrx*KERB_W*0.5, oy-ty2*sl+nry*KERB_W*0.5, 0),
              (ox+tx2*sl+nrx*KERB_W*0.5, oy+ty2*sl+nry*KERB_W*0.5, 0),
              (ox+tx2*sl-nrx*KERB_W*0.5, oy+ty2*sl-nry*KERB_W*0.5, 0),
              (ox-tx2*sl-nrx*KERB_W*0.5, oy-ty2*sl-nry*KERB_W*0.5, h),
              (ox-tx2*sl+nrx*KERB_W*0.5, oy-ty2*sl+nry*KERB_W*0.5, h),
              (ox+tx2*sl+nrx*KERB_W*0.5, oy+ty2*sl+nry*KERB_W*0.5, h),
              (ox+tx2*sl-nrx*KERB_W*0.5, oy+ty2*sl-nry*KERB_W*0.5, h)]
        kf = [(0,1,2,3),(4,5,6,7),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
        km = bpy.data.meshes.new(f"kerb_{kerb_count}")
        km.from_pydata(kv,[],kf); km.update()
        ko = bpy.data.objects.new(f"kerb_{kerb_count}",km)
        bpy.context.scene.collection.objects.link(ko)
        ko.data.materials.append(mk)
        kerb_count += 1
    seg_idx += 1

print(f"  Kerbs: {kerb_count} segments")

# ── BARRIERS ──────────────────────────────────────────────────────────────────
print("[Build] Building barriers…")
BOFF = TRACK_WIDTH/2 + 0.6; BH = 0.9
for side_name, side_sign in [("outer",-1),("inner",1)]:
    bvs=[]; bfs=[]
    for i in range(N):
        cx,cy=center[i]; nrx,nry=normal_at(center,i)
        ox=cx+side_sign*BOFF*nrx; oy=cy+side_sign*BOFF*nry
        bvs.append((ox,oy,0)); bvs.append((ox,oy,BH))
    for i in range(N-1):
        a,b,c,d=i*2,i*2+1,(i+1)*2,(i+1)*2+1
        bfs.append((a,c,d,b))
    bme2=bpy.data.meshes.new(f"barrier_{side_name}")
    bme2.from_pydata(bvs,[],bfs); bme2.update()
    bobj2=bpy.data.objects.new(f"barrier_{side_name}",bme2)
    bpy.context.scene.collection.objects.link(bobj2)
    bobj2.data.materials.append(MAT_BARRIER)

# ── EXPORT ────────────────────────────────────────────────────────────────────
print("\n[Export] Enabling FBX…")
fbx_ok = False
try:
    import addon_utils
    addon_utils.enable("io_scene_fbx", default_set=True, persistent=True)
    fbx_ok = hasattr(bpy.ops.export_scene, "fbx")
    print(f"  FBX: {'enabled' if fbx_ok else 'not available'}")
except Exception as e:
    print(f"  FBX: {e}")

all_mesh = [o for o in bpy.context.scene.collection.objects
            if o.type=='MESH' and o.name!="satellite_background"]
kerb_objs = [o for o in all_mesh if o.name.startswith("kerb_")]
road_objs  = [o for o in all_mesh if o.name in ("track_surface","start_line")]
barr_objs  = [o for o in all_mesh if o.name.startswith("barrier_")]

def export_sel(objs, path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        try: o.select_set(True); bpy.context.view_layer.objects.active=o
        except: pass
    if fbx_ok:
        try:
            bpy.ops.export_scene.fbx(
                filepath=path, use_selection=True,
                global_scale=1.0, axis_forward='-Z', axis_up='Y',
                apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
                bake_space_transform=True, mesh_smooth_type='FACE',
                use_mesh_modifiers=True, add_leaf_bones=False,
            ); print(f"  → {os.path.basename(path)}"); return
        except Exception as e: print(f"  FBX err: {e}")
    obj_path = path.replace(".fbx",".obj")
    try:
        bpy.ops.wm.obj_export(
            filepath=obj_path, export_selected_objects=True,
            forward_axis='NEGATIVE_Z', up_axis='Y',
            apply_modifiers=True, export_materials=True,
        ); print(f"  → {os.path.basename(obj_path)}")
    except Exception as e2: print(f"  OBJ err: {e2}")

export_sel(all_mesh,  os.path.join(OUTPUT_DIR,"track_mesh.fbx"))
export_sel(road_objs, os.path.join(OUTPUT_DIR,"track_surface.fbx"))
export_sel([terrain], os.path.join(OUTPUT_DIR,"terrain.fbx"))
if kerb_objs: export_sel(kerb_objs, os.path.join(OUTPUT_DIR,"curbs.fbx"))
if barr_objs: export_sel(barr_objs, os.path.join(OUTPUT_DIR,"barriers.fbx"))

print(f"""
╔════════════════════════════════════════════════════════════╗
║  BUILD COMPLETE — Stockholm Karting Center                 ║
║  Length  : {total_m:>6.0f}m traced                             ║
║  Kerbs   : {kerb_count:>4d} segments                               ║
║  Output  : content/tracks/stockholm_karting/models/        ║
╚════════════════════════════════════════════════════════════╝
Next: Open ksEditor → import track_mesh.fbx → compile .kn5
""")
