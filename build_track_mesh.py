"""
Stockholm Karting Center — Assetto Corsa Track Mesh Builder
Rebuilt 2026-03-06 using Blender Bezier curves for smooth geometry.
Track layout traced from satellite imagery.
"""

import bpy
import math
import os

# ── CONFIG ───────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "content", "tracks", "stockholm_karting", "models")
TRACK_WIDTH = 7.92   # 26 feet in meters
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── TRACK WAYPOINTS (local meters, X=east, Y=north) ─────────────────────────
# Traced from satellite imagery. Counter-clockwise direction.
# Front straight runs E-W at Y=0 (north edge). Track extends south.
#
# Layout:
#   Front straight (north, E-W)
#   → NE sweeper turning south
#   → East side heading south
#   → Large SE oval loop (main feature, grass infield)
#   → Exit oval heading northwest
#   → Center flowing S-bends
#   → NW tight complex
#   → West side heading back east along north
#   → Front straight
#
# Each tuple: (x, y) in meters

WAYPOINTS = [
    # Front straight (W → E)
    (-110,   5),
    ( -80,   5),
    ( -40,   5),
    (   0,   5),
    (  40,   5),
    (  80,   5),
    ( 110,   5),

    # NE corner sweeper (right turn, heading south)
    ( 130, -10),
    ( 140, -30),
    ( 140, -60),

    # East side straight (heading south)
    ( 138, -90),
    ( 132,-115),

    # Oval entry — sweeping right into the oval (SE feature)
    ( 120,-130),
    ( 100,-148),
    (  70,-158),
    (  40,-162),
    (  10,-160),

    # Oval south — wrapping around the bottom (tight right)
    ( -20,-155),
    ( -45,-142),
    ( -60,-125),

    # Oval exit — heading northwest
    ( -60,-105),
    ( -52, -88),
    ( -40, -75),

    # Center S-bends (flowing, not tight)
    ( -20, -65),
    (   5, -58),
    (  20, -50),
    (  10, -40),
    ( -10, -32),

    # NW tight complex
    ( -40, -25),
    ( -70, -22),
    ( -95, -18),
    (-115, -12),

    # Back to front straight
    (-115,  -2),
    (-110,   5),
]

print(f"\n[Build] Stockholm Karting Center — Bezier curve method")
print(f"[Build] Waypoints: {len(WAYPOINTS)}")

# ── CLEAR SCENE ──────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
for col in bpy.data.collections:
    bpy.data.collections.remove(col)

# ── MATERIALS ────────────────────────────────────────────────────────────────
def make_mat(name, r, g, b, roughness=0.85):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
        bsdf.inputs["Roughness"].default_value  = roughness
    return mat

mat_asphalt  = make_mat("road_asphalt",  0.10, 0.10, 0.10, 0.9)
mat_grass    = make_mat("grass_terrain",  0.22, 0.48, 0.17, 0.9)
mat_kerb_r   = make_mat("kerb_red",       0.80, 0.05, 0.05, 0.7)
mat_kerb_w   = make_mat("kerb_white",     0.92, 0.92, 0.92, 0.7)
mat_barrier  = make_mat("barrier_concrete",0.55, 0.55, 0.55, 0.9)
mat_pit      = make_mat("pit_surface",    0.22, 0.22, 0.22, 0.9)

print("[Build] Materials created.")

# ── BEZIER CURVE TRACK ───────────────────────────────────────────────────────
def build_track_from_bezier(waypoints, width, name="track_surface"):
    """Create smooth track surface using Blender Bezier curve → mesh."""
    # Create curve object
    curve_data = bpy.data.curves.new(name=f"{name}_curve", type='CURVE')
    curve_data.dimensions = '2D'
    curve_data.fill_mode  = 'NONE'

    spline = curve_data.splines.new('BEZIER')
    spline.bezier_points.add(len(waypoints) - 1)
    spline.use_cyclic_u = True

    for i, (x, y) in enumerate(waypoints):
        bp = spline.bezier_points[i]
        bp.co = (x, y, 0)
        bp.handle_left_type  = 'AUTO'
        bp.handle_right_type = 'AUTO'

    curve_data.resolution_u = 12   # smoothness per segment

    # Convert to mesh by adding bevel for width
    # Use extrude along normals approach: create mesh manually from evaluated curve
    curve_obj = bpy.data.objects.new(f"{name}_curve_obj", curve_data)
    bpy.context.scene.collection.objects.link(curve_obj)
    bpy.context.view_layer.objects.active = curve_obj
    curve_obj.select_set(True)

    # Get evaluated points
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj  = curve_obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()

    # Extract centerline vertices from evaluated curve
    center_pts = [(v.co.x, v.co.y) for v in eval_mesh.vertices]
    eval_obj.to_mesh_clear()

    # Remove curve object
    bpy.data.objects.remove(curve_obj)
    bpy.data.curves.remove(curve_data)

    if len(center_pts) < 3:
        print(f"  [WARN] Only {len(center_pts)} center pts — falling back to waypoints")
        center_pts = [(x, y) for x, y in waypoints]

    n = len(center_pts)
    half_w = width / 2.0

    verts  = []
    faces  = []

    # Compute normals
    def perp_normal(pts, i):
        a = pts[(i - 1) % len(pts)]
        b = pts[(i + 1) % len(pts)]
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        length = math.sqrt(dx*dx + dy*dy) or 1.0
        return (-dy/length, dx/length)

    for i in range(n):
        cx, cy = center_pts[i]
        nx, ny = perp_normal(center_pts, i)
        # Left edge (outer)
        verts.append((cx - nx * half_w, cy - ny * half_w, 0))
        # Right edge (inner)
        verts.append((cx + nx * half_w, cy + ny * half_w, 0))

    # Faces (quad strips)
    for i in range(n):
        i0 = i * 2
        i1 = i * 2 + 1
        i2 = ((i + 1) % n) * 2
        i3 = ((i + 1) % n) * 2 + 1
        faces.append((i0, i1, i3, i2))

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat_asphalt)
    return obj, center_pts

print("[Build] Building track surface (Bezier method)…")
track_obj, center_pts = build_track_from_bezier(WAYPOINTS, TRACK_WIDTH)
n_pts = len(center_pts)
print(f"  Track surface built: {n_pts} evaluated points")

# Calculate approximate length
total_len = 0
for i in range(n_pts):
    a = center_pts[i]
    b = center_pts[(i+1) % n_pts]
    dx = b[0]-a[0]; dy = b[1]-a[1]
    total_len += math.sqrt(dx*dx + dy*dy)
print(f"  Approx length: {total_len:.0f}m")

# ── PIT LANE (parallel to front straight, offset north 12m) ──────────────────
print("[Build] Building pit lane…")
pit_verts = [
    (-115, 12, 0), (-115, 16, 0),
    ( 110, 12, 0), ( 110, 16, 0),
]
pit_faces = [(0, 1, 3, 2)]
pit_mesh  = bpy.data.meshes.new("pit_surface")
pit_mesh.from_pydata(pit_verts, [], pit_faces)
pit_mesh.update()
pit_obj = bpy.data.objects.new("pit_surface", pit_mesh)
bpy.context.scene.collection.objects.link(pit_obj)
pit_obj.data.materials.append(mat_pit)

# ── TERRAIN ───────────────────────────────────────────────────────────────────
print("[Build] Building terrain…")
SIZE = 400
GRID = 16
bpy.ops.mesh.primitive_grid_add(
    x_subdivisions=GRID, y_subdivisions=GRID,
    size=1,
    location=(0, -80, -0.05)
)
terrain_obj = bpy.context.active_object
terrain_obj.name = "terrain"
terrain_obj.scale = (SIZE, SIZE, 1)
bpy.ops.object.transform_apply(scale=True)
terrain_obj.data.materials.append(mat_grass)

# ── KERBS ─────────────────────────────────────────────────────────────────────
print("[Build] Building kerbs…")

def perp_normal_pts(pts, i):
    n = len(pts)
    a = pts[(i-1) % n]
    b = pts[(i+1) % n]
    dx = b[0]-a[0]; dy = b[1]-a[1]
    length = math.sqrt(dx*dx+dy*dy) or 1.0
    return (-dy/length, dx/length)

def local_radius(pts, i):
    n = len(pts)
    a = pts[(i-1)%n]; b = pts[i]; c = pts[(i+1)%n]
    ax,ay = b[0]-a[0], b[1]-a[1]
    bx,by = c[0]-b[0], c[1]-b[1]
    cross = abs(ax*by - ay*bx)
    if cross < 1e-6: return 9999
    la = math.sqrt(ax*ax+ay*ay)
    lb = math.sqrt(bx*bx+by*by)
    return (la+lb)/2 / (2*math.asin(min(cross/(la*lb+1e-9), 1.0)) or 1e-9)

kerb_objects = []
KERB_W   = 0.3
KERB_H   = 0.03
SEG_LEN  = 1.5
half_w   = TRACK_WIDTH / 2.0

seg_i = 0
i = 0
while i < n_pts:
    r = local_radius(center_pts, i)
    if r < 60:   # corner detected
        side = 1 if r < 30 else 0   # tight = inside kerb raised
        cx, cy = center_pts[i]
        nx, ny = perp_normal_pts(center_pts, i)

        for side_sign, mat in [(-1, mat_kerb_r if seg_i % 2 == 0 else mat_kerb_w),
                                 (1,  mat_kerb_w if seg_i % 2 == 0 else mat_kerb_r)]:
            ox = cx + side_sign * (half_w + KERB_W/2) * nx
            oy = cy + side_sign * (half_w + KERB_W/2) * ny

            # Next point for orientation
            nx2, ny2 = perp_normal_pts(center_pts, (i+1)%n_pts)
            tx = center_pts[(i+1)%n_pts][0] - cx
            ty = center_pts[(i+1)%n_pts][1] - cy
            tl = math.sqrt(tx*tx+ty*ty) or 1.0
            tx /= tl; ty /= tl

            h = KERB_H if r < 30 else 0.01

            kv = [
                (ox - tx*SEG_LEN/2 - nx*KERB_W/2, oy - ty*SEG_LEN/2 - ny*KERB_W/2, 0),
                (ox - tx*SEG_LEN/2 + nx*KERB_W/2, oy - ty*SEG_LEN/2 + ny*KERB_W/2, 0),
                (ox + tx*SEG_LEN/2 + nx*KERB_W/2, oy + ty*SEG_LEN/2 + ny*KERB_W/2, 0),
                (ox + tx*SEG_LEN/2 - nx*KERB_W/2, oy + ty*SEG_LEN/2 - ny*KERB_W/2, 0),
                (ox - tx*SEG_LEN/2 - nx*KERB_W/2, oy - ty*SEG_LEN/2 - ny*KERB_W/2, h),
                (ox - tx*SEG_LEN/2 + nx*KERB_W/2, oy - ty*SEG_LEN/2 + ny*KERB_W/2, h),
                (ox + tx*SEG_LEN/2 + nx*KERB_W/2, oy + ty*SEG_LEN/2 + ny*KERB_W/2, h),
                (ox + tx*SEG_LEN/2 - nx*KERB_W/2, oy + ty*SEG_LEN/2 - ny*KERB_W/2, h),
            ]
            kf = [(0,1,2,3),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
            km = bpy.data.meshes.new(f"kerb_{seg_i}_{side_sign}")
            km.from_pydata(kv, [], kf); km.update()
            ko = bpy.data.objects.new(f"kerb_{seg_i}_{side_sign}", km)
            bpy.context.scene.collection.objects.link(ko)
            ko.data.materials.append(mat)
            kerb_objects.append(ko)

        seg_i += 1
        i += 3  # skip ahead to avoid duplicate kerbs
    else:
        i += 1

print(f"  Kerb segments: {seg_i}")

# ── BARRIERS ──────────────────────────────────────────────────────────────────
print("[Build] Building barriers…")

def build_barrier(pts, offset, name):
    n = len(pts)
    verts = []; faces = []
    for i in range(n):
        cx, cy = pts[i]
        nx, ny = perp_normal_pts(pts, i)
        ox = cx + offset * nx
        oy = cy + offset * ny
        verts.append((ox, oy, 0.0))
        verts.append((ox, oy, 0.8))
    for i in range(n):
        i0 = i*2; i1 = i*2+1
        i2 = ((i+1)%n)*2; i3 = ((i+1)%n)*2+1
        faces.append((i0,i2,i3,i1))
    bm = bpy.data.meshes.new(name)
    bm.from_pydata(verts,[],faces); bm.update()
    bo = bpy.data.objects.new(name, bm)
    bpy.context.scene.collection.objects.link(bo)
    bo.data.materials.append(mat_barrier)
    return bo

barrier_outer = build_barrier(center_pts,  (TRACK_WIDTH/2 + 0.5), "barrier_outer")
barrier_inner = build_barrier(center_pts, -(TRACK_WIDTH/2 + 0.5), "barrier_inner")
barrier_objects = [barrier_outer, barrier_inner]
print("  Barriers built.")

# ── ENABLE FBX + EXPORT ───────────────────────────────────────────────────────
print("\n[Export] Exporting FBX files…")

fbx_available = False
try:
    import addon_utils
    addon_utils.enable("io_scene_fbx", default_set=True, persistent=True)
    fbx_available = hasattr(bpy.ops.export_scene, 'fbx')
    print(f"  FBX exporter: {'enabled' if fbx_available else 'not available'}")
except Exception as e:
    print(f"  FBX addon: {e}")

def export_objects(objs, filepath):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        if o and o.name in bpy.data.objects:
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
    if fbx_available:
        try:
            bpy.ops.export_scene.fbx(
                filepath=filepath, use_selection=True,
                global_scale=1.0, axis_forward='-Z', axis_up='Y',
                apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
                bake_space_transform=True, mesh_smooth_type='FACE',
                use_mesh_modifiers=True, add_leaf_bones=False,
                path_mode='COPY', embed_textures=False,
            )
            print(f"    → {filepath}")
            return
        except Exception as e:
            print(f"    FBX failed ({e}), trying OBJ…")
    obj_path = filepath.replace(".fbx", ".obj")
    try:
        bpy.ops.wm.obj_export(
            filepath=obj_path, export_selected_objects=True,
            forward_axis='NEGATIVE_Z', up_axis='Y',
            apply_modifiers=True, export_materials=True,
        )
        print(f"    → {obj_path} (OBJ)")
    except Exception as e2:
        print(f"    OBJ also failed: {e2}")

all_objs = [track_obj, terrain_obj, pit_obj] + kerb_objects + barrier_objects
export_objects(all_objs,           os.path.join(OUTPUT_DIR, "track_mesh.fbx"))
export_objects([track_obj],        os.path.join(OUTPUT_DIR, "track_surface.fbx"))
export_objects([terrain_obj],      os.path.join(OUTPUT_DIR, "terrain.fbx"))
export_objects(kerb_objects,       os.path.join(OUTPUT_DIR, "curbs.fbx"))
export_objects(barrier_objects,    os.path.join(OUTPUT_DIR, "barriers.fbx"))

print(f"\n✅ Export complete → {OUTPUT_DIR}")
print(f"\n═══════════════════════════════════════════════")
print(f"  Stockholm Karting Center — Build Complete")
print(f"  Track length  : {total_len:.0f}m")
print(f"  Track width   : {TRACK_WIDTH}m")
print(f"  Curve pts     : {n_pts}")
print(f"  Kerb segments : {seg_i}")
print(f"═══════════════════════════════════════════════")
print("\nDone. Open Blender to inspect before compiling to .kn5.")
