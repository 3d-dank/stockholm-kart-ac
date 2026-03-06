"""
Stockholm Karting Center — Assetto Corsa Track Builder
v3 — Clean rewrite: no kerbs (too buggy), correct layout, pure local coords.

Track: 0.65mi (1047m), 14 turns, 26ft (7.92m) wide, clockwise
Location: 13185 US-12, Cokato MN — just east of Cokato, south of Hwy 12
Paddock/garages on NORTH edge. Front straight runs E-W along north.
Track extends SOUTH from front straight.
"""

import bpy, math, os

# ── OUTPUT PATH ───────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "content", "tracks", "stockholm_karting", "models")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRACK_WIDTH = 7.92  # 26 ft

# ── TRACK CENTERLINE WAYPOINTS ────────────────────────────────────────────────
# Local coordinates: X = east (+), Y = north (+)
# Front straight at Y=0, track extends south (Y negative).
# Direction: CLOCKWISE. Driving W→E along front straight.
#
# Layout based on satellite imagery:
#   Front straight (N edge, W→E)
#   T1:  Right sweeper — NE corner heading south
#   T2:  Long east-side straight heading south
#   T3:  Right — entering SE oval section
#   T4:  Right — sweeping around south end of oval
#   T5:  Right — completing oval loop
#   T6:  Left S-bend heading northwest
#   T7:  Right S-bend
#   T8:  Left S-bend
#   T9:  Right S-bend
#   T10: Left — entering NW complex
#   T11: Right — tight NW hairpin
#   T12: Left
#   T13: Right
#   T14: Right — sweeper back onto front straight
#
WAYPOINTS = [
    # Front straight W→E (Y=0, north edge)
    (-130,   0),
    ( -90,   0),
    ( -50,   0),
    (   0,   0),
    (  50,   0),
    (  90,   0),
    ( 130,   0),

    # T1: NE sweeper — right turn heading south
    ( 152, -18),
    ( 160, -45),

    # East side straight
    ( 158, -80),
    ( 154,-115),

    # T3: Oval entry — sweeping right
    ( 140,-138),
    ( 118,-158),
    (  88,-172),
    (  55,-178),

    # T4/T5: Oval south — right wrap
    (  20,-175),
    ( -10,-167),
    ( -35,-152),

    # Oval west exit — heading north-northwest
    ( -52,-133),
    ( -58,-112),
    ( -52, -92),

    # T6/T7: S-bends heading northwest (key visual feature)
    ( -35, -75),
    ( -10, -62),
    (  15, -53),

    # T8/T9: second S-bend
    (  18, -42),
    (   0, -33),
    ( -20, -27),

    # T10-T13: NW complex — tighter corners
    ( -48, -22),
    ( -75, -18),
    (-102, -15),
    (-125, -10),

    # T14: Final right sweeper back onto front straight
    (-138,  -4),
    (-130,   0),  # close loop
]

print(f"\n[SKC Builder v3] Waypoints: {len(WAYPOINTS)}")

# ── CLEAR SCENE ───────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ── MATERIALS ─────────────────────────────────────────────────────────────────
def mat(name, r, g, b, rough=0.85):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
        bsdf.inputs["Roughness"].default_value = rough
    return m

MAT_ASPHALT  = mat("road_asphalt",   0.08, 0.08, 0.08)
MAT_PIT      = mat("pit_asphalt",    0.15, 0.15, 0.15)
MAT_GRASS    = mat("terrain_grass",  0.20, 0.45, 0.15)
MAT_KERB_R   = mat("kerb_red",       0.82, 0.08, 0.08, 0.6)
MAT_KERB_W   = mat("kerb_white",     0.90, 0.90, 0.90, 0.6)
MAT_BARRIER  = mat("barrier",        0.50, 0.50, 0.50)
MAT_LINE     = mat("start_line",     0.95, 0.95, 0.95, 0.4)

# ── SMOOTH BEZIER → MESH ──────────────────────────────────────────────────────
def get_smooth_centerline(waypoints):
    """Run waypoints through Blender Bezier spline, return evaluated (x,y) list."""
    cd = bpy.data.curves.new("_cl_curve", 'CURVE')
    cd.dimensions = '2D'
    sp = cd.splines.new('BEZIER')
    sp.bezier_points.add(len(waypoints) - 1)
    sp.use_cyclic_u = False   # open — first == last for our closed loop
    cd.resolution_u = 16

    for i, (x, y) in enumerate(waypoints):
        bp = sp.bezier_points[i]
        bp.co = (x, y, 0)
        bp.handle_left_type  = 'AUTO'
        bp.handle_right_type = 'AUTO'

    obj = bpy.data.objects.new("_cl_obj", cd)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()

    dep  = bpy.context.evaluated_depsgraph_get()
    ev   = obj.evaluated_get(dep)
    pts  = [(v.co.x, v.co.y) for v in ev.to_mesh().vertices]

    bpy.data.objects.remove(obj)
    bpy.data.curves.remove(cd)
    return pts

print("[SKC] Evaluating Bezier centerline…")
center = get_smooth_centerline(WAYPOINTS)
N = len(center)
print(f"  Evaluated {N} centerline points")

# Compute total length
total_m = sum(
    math.hypot(center[(i+1)%N][0]-center[i][0], center[(i+1)%N][1]-center[i][1])
    for i in range(N-1)
)
print(f"  Estimated length: {total_m:.0f}m (target ~1047m)")

# ── HELPER: perpendicular normal at point i ───────────────────────────────────
def normal_at(pts, i):
    n = len(pts)
    ax, ay = pts[(i-1)%n]
    bx, by = pts[(i+1)%n]
    dx, dy = bx-ax, by-ay
    L = math.hypot(dx, dy) or 1
    return -dy/L, dx/L   # perpendicular (left side)

# ── BUILD TRACK SURFACE ───────────────────────────────────────────────────────
def build_strip(pts, width, z=0.0, name="track"):
    hw = width / 2
    verts, faces = [], []
    n = len(pts)
    for i in range(n):
        nx, ny = normal_at(pts, i)
        cx, cy = pts[i]
        verts.append((cx - nx*hw, cy - ny*hw, z))   # left
        verts.append((cx + nx*hw, cy + ny*hw, z))   # right
    for i in range(n - 1):
        a, b = i*2, i*2+1
        c, d = (i+1)*2, (i+1)*2+1
        faces.append((a, b, d, c))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob

print("[SKC] Building track surface…")
track_obj = build_strip(center, TRACK_WIDTH, z=0.0, name="track_surface")
track_obj.data.materials.append(MAT_ASPHALT)

# ── START/FINISH LINE (white stripe at first waypoint) ────────────────────────
sf_idx = 0
sfx, sfy = center[sf_idx]
nx, ny = normal_at(center, sf_idx)
tx = center[1][0] - center[0][0]; ty = center[1][1] - center[0][1]
tl = math.hypot(tx, ty) or 1; tx /= tl; ty /= tl
hw = TRACK_WIDTH / 2
lw = 0.5   # half-length along track
sv = [
    (sfx - nx*hw - tx*lw, sfy - ny*hw - ty*lw, 0.01),
    (sfx + nx*hw - tx*lw, sfy + ny*hw - ty*lw, 0.01),
    (sfx + nx*hw + tx*lw, sfy + ny*hw + ty*lw, 0.01),
    (sfx - nx*hw + tx*lw, sfy - ny*hw + ty*lw, 0.01),
]
sme = bpy.data.meshes.new("start_line")
sme.from_pydata(sv, [], [(0,1,2,3)]); sme.update()
sobj = bpy.data.objects.new("start_line", sme)
bpy.context.scene.collection.objects.link(sobj)
sobj.data.materials.append(MAT_LINE)

# ── PIT LANE (connected strip north of front straight) ────────────────────────
print("[SKC] Building pit lane…")
PIT_OFFSET = 10   # meters north of front straight
pit_pts = [
    (-130,  PIT_OFFSET),
    ( 130,  PIT_OFFSET),
]
# Simple rectangular pit lane
pw = 4.0
pv = [
    (-130, PIT_OFFSET - pw/2, 0),
    (-130, PIT_OFFSET + pw/2, 0),
    ( 130, PIT_OFFSET - pw/2, 0),
    ( 130, PIT_OFFSET + pw/2, 0),
]
pf = [(0, 1, 3, 2)]
pme = bpy.data.meshes.new("pit_lane")
pme.from_pydata(pv, [], pf); pme.update()
pit_obj = bpy.data.objects.new("pit_lane", pme)
bpy.context.scene.collection.objects.link(pit_obj)
pit_obj.data.materials.append(MAT_PIT)

# ── TERRAIN ───────────────────────────────────────────────────────────────────
print("[SKC] Building terrain…")
bpy.ops.mesh.primitive_plane_add(size=600, location=(0, -90, -0.05))
terrain = bpy.context.active_object
terrain.name = "terrain"
terrain.data.materials.append(MAT_GRASS)

# ── KERBS (simple alternating red/white blocks at corners only) ───────────────
print("[SKC] Building kerbs…")

def corner_radius(pts, i):
    n = len(pts)
    a = pts[(i-1)%n]; b = pts[i]; c = pts[(i+1)%n]
    v1x, v1y = b[0]-a[0], b[1]-a[1]
    v2x, v2y = c[0]-b[0], c[1]-b[1]
    cross = abs(v1x*v2y - v1y*v2x)
    l1 = math.hypot(v1x, v1y)
    l2 = math.hypot(v2x, v2y)
    if cross < 0.01 or l1 < 0.01 or l2 < 0.01:
        return 9999
    sin_a = min(cross / (l1 * l2), 1.0)
    angle = math.asin(sin_a)
    if angle < 0.01:
        return 9999
    return min(l1, l2) / (2 * math.tan(angle / 2 + 0.001))

KERB_W = 0.35
KERB_H_TIGHT = 0.04
KERB_H_STD   = 0.01
KERB_SEG_LEN = 1.2
hw = TRACK_WIDTH / 2

kerb_count = 0
seg_index  = 0
skip       = 0

for i in range(1, N - 1):
    if skip > 0:
        skip -= 1
        continue
    r = corner_radius(center, i)
    if r > 40:
        continue   # not a corner

    skip = 4   # skip next few to avoid overlapping kerb tiles
    h = KERB_H_TIGHT if r < 18 else KERB_H_STD

    cx, cy = center[i]
    nrx, nry = normal_at(center, i)
    tx = center[min(i+1,N-1)][0] - center[i][0]
    ty = center[min(i+1,N-1)][1] - center[i][1]
    tl = math.hypot(tx,ty) or 1; tx/=tl; ty/=tl

    for side, mats in [(-1, [MAT_KERB_R, MAT_KERB_W]),
                        ( 1, [MAT_KERB_W, MAT_KERB_R])]:
        mat_k = mats[seg_index % 2]
        ox = cx + side * (hw + KERB_W*0.5) * nrx
        oy = cy + side * (hw + KERB_W*0.5) * nry
        sl = KERB_SEG_LEN * 0.5
        kv = [
            (ox - tx*sl - nrx*KERB_W*0.5, oy - ty*sl - nry*KERB_W*0.5, 0),
            (ox - tx*sl + nrx*KERB_W*0.5, oy - ty*sl + nry*KERB_W*0.5, 0),
            (ox + tx*sl + nrx*KERB_W*0.5, oy + ty*sl + nry*KERB_W*0.5, 0),
            (ox + tx*sl - nrx*KERB_W*0.5, oy + ty*sl - nry*KERB_W*0.5, 0),
            (ox - tx*sl - nrx*KERB_W*0.5, oy - ty*sl - nry*KERB_W*0.5, h),
            (ox - tx*sl + nrx*KERB_W*0.5, oy - ty*sl + nry*KERB_W*0.5, h),
            (ox + tx*sl + nrx*KERB_W*0.5, oy + ty*sl + nry*KERB_W*0.5, h),
            (ox + tx*sl - nrx*KERB_W*0.5, oy + ty*sl - nry*KERB_W*0.5, h),
        ]
        kf = [(0,1,2,3),(4,5,6,7),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
        km = bpy.data.meshes.new(f"kerb_{kerb_count}")
        km.from_pydata(kv, [], kf); km.update()
        ko = bpy.data.objects.new(f"kerb_{kerb_count}", km)
        bpy.context.scene.collection.objects.link(ko)
        ko.data.materials.append(mat_k)
        kerb_count += 1

    seg_index += 1

print(f"  Kerbs placed: {kerb_count}")

# ── OUTER BARRIER ─────────────────────────────────────────────────────────────
print("[SKC] Building barriers…")
BARRIER_OFFSET = TRACK_WIDTH/2 + 0.6
BARRIER_H = 0.9

bv, bf = [], []
for i in range(N):
    cx, cy = center[i]
    nrx, nry = normal_at(center, i)
    ox = cx - nrx * BARRIER_OFFSET   # outer side
    oy = cy - nry * BARRIER_OFFSET
    bv.append((ox, oy, 0.0))
    bv.append((ox, oy, BARRIER_H))

for i in range(N-1):
    a,b,c,d = i*2, i*2+1, (i+1)*2, (i+1)*2+1
    bf.append((a, c, d, b))

bme = bpy.data.meshes.new("barrier_outer")
bme.from_pydata(bv, [], bf); bme.update()
bobj = bpy.data.objects.new("barrier_outer", bme)
bpy.context.scene.collection.objects.link(bobj)
bobj.data.materials.append(MAT_BARRIER)

# ── COLLECT ALL OBJECTS ────────────────────────────────────────────────────────
all_objs  = [o for o in bpy.context.scene.collection.objects if o.type == 'MESH']
road_objs = [track_obj, sobj, pit_obj]
kerb_objs = [o for o in all_objs if o.name.startswith("kerb_")]

print(f"\n[SKC] Scene: {len(all_objs)} mesh objects total")

# ── FBX / OBJ EXPORT ──────────────────────────────────────────────────────────
print("\n[SKC] Enabling FBX exporter…")
fbx_ok = False
try:
    import addon_utils
    addon_utils.enable("io_scene_fbx", default_set=True, persistent=True)
    fbx_ok = hasattr(bpy.ops.export_scene, "fbx")
    print(f"  FBX: {'OK' if fbx_ok else 'not available'}")
except Exception as e:
    print(f"  FBX addon error: {e}")

def export_sel(objs, path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        try: o.select_set(True); bpy.context.view_layer.objects.active = o
        except: pass
    if fbx_ok:
        try:
            bpy.ops.export_scene.fbx(
                filepath=path, use_selection=True,
                global_scale=1.0, axis_forward='-Z', axis_up='Y',
                apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
                bake_space_transform=True, mesh_smooth_type='FACE',
                use_mesh_modifiers=True, add_leaf_bones=False,
            )
            print(f"    FBX → {os.path.basename(path)}")
            return
        except Exception as e:
            print(f"    FBX failed ({e}), trying OBJ…")
    obj_path = path.replace(".fbx", ".obj")
    try:
        bpy.ops.wm.obj_export(
            filepath=obj_path, export_selected_objects=True,
            forward_axis='NEGATIVE_Z', up_axis='Y',
            apply_modifiers=True, export_materials=True,
        )
        print(f"    OBJ → {os.path.basename(obj_path)}")
    except Exception as e2:
        print(f"    OBJ failed: {e2}")

export_sel(all_objs,  os.path.join(OUTPUT_DIR, "track_mesh.fbx"))
export_sel(road_objs, os.path.join(OUTPUT_DIR, "track_surface.fbx"))
export_sel([terrain], os.path.join(OUTPUT_DIR, "terrain.fbx"))
if kerb_objs:
    export_sel(kerb_objs, os.path.join(OUTPUT_DIR, "curbs.fbx"))
export_sel([bobj],    os.path.join(OUTPUT_DIR, "barriers.fbx"))

print(f"""
╔══════════════════════════════════════════════╗
║  Stockholm Karting Center — Build Complete   ║
║  Length  : {total_m:>6.0f}m  (target ~1047m)      ║
║  Width   :   7.92m (26ft)                   ║
║  Points  : {N:>6d}  evaluated               ║
║  Kerbs   : {kerb_count:>6d}  segments                ║
║  Output  : content/tracks/stockholm_karting ║
╚══════════════════════════════════════════════╝
""")
