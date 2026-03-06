"""
Stockholm Karting Center — Assetto Corsa Track Mesh Builder
============================================================
Blender Python script (bpy) — Run via: blender --background --python build_track_mesh.py

Builds:
  • Full asphalt track surface (7.92m wide, ~1048m long, 14 turns)
  • Terrain ground plane (200m x 200m, elevation-displaced)
  • Permanent edge kerbs (inside & outside at each corner apex)
  • Permanent concrete/armco outer boundary barriers
  • 6 Assetto Corsa-ready materials

NOTE: NO layout-defining tire barriers, chicanes, or redirectors.
      The full racing surface is clean and open. Jeff handles layouts manually in AC.

Track: 13185 US Hwy 12 SW, Cokato MN 55321
GPS center: 45.0772°N, 94.1858°W
Author: TopDog AI / Highlands
"""

import bpy
import bmesh
import math
import json
import csv
import os
from mathutils import Vector, Matrix

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
GEOJSON_PATH = os.path.join(SCRIPT_DIR, "track_centerline.geojson")
ELEV_PATH    = os.path.join(SCRIPT_DIR, "elevation_profile.csv")
OUTPUT_DIR   = os.path.join(SCRIPT_DIR, "content", "tracks", "stockholm_karting", "models")

GPS_CENTER_LAT =  45.0772
GPS_CENTER_LON = -94.1858
EARTH_RADIUS_M =  6371000.0

TRACK_WIDTH       = 7.92    # metres (26 ft)
HALF_WIDTH        = TRACK_WIDTH / 2.0   # 3.96m

KERB_INNER_WIDTH  = 0.30    # metres
KERB_INNER_RAISE  = 0.03    # metres — raised inside apex kerbs
KERB_OUTER_WIDTH  = 0.20    # metres — flat exit kerbs
KERB_OUTER_RAISE  = 0.005   # metres — nearly flush

BARRIER_OFFSET    = 1.50    # metres beyond track edge
BARRIER_CONCRETE_H = 0.50   # metres
BARRIER_TIRE_H     = 0.50   # metres (stacked on top of concrete)

TERRAIN_SIZE      = 200.0   # metres square
TERRAIN_GRID      = 20      # subdivisions each axis
TRACK_RAISE       = 0.05    # metres track sits above terrain

# Corner radius thresholds (metres)
CORNER_TIGHT_R    = 30.0
CORNER_MEDIUM_R   = 60.0

# Kerb segment count per corner (alternating red/white stripes)
KERB_SEGS         = 8

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# 1. COORDINATE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def latlon_to_xy(lat, lon):
    """Equirectangular projection → local X (east), Y (north) in metres."""
    lat_rad = math.radians(GPS_CENTER_LAT)
    x = math.radians(lon - GPS_CENTER_LON) * math.cos(lat_rad) * EARTH_RADIUS_M
    y = math.radians(lat - GPS_CENTER_LAT) * EARTH_RADIUS_M
    return x, y


def vec2(x, y):
    return Vector((x, y))


def perp2(v):
    """2-D perpendicular (rotated 90° CCW)."""
    return Vector((-v.y, v.x))


def normalise2(v):
    l = v.length
    if l < 1e-9:
        return Vector((1, 0))
    return v / l

# ─────────────────────────────────────────────────────────────────────────────
# 2. LOAD & CONVERT GEOJSON CENTERLINE
# ─────────────────────────────────────────────────────────────────────────────

print("\n[1/8] Loading GeoJSON centerline …")

with open(GEOJSON_PATH, "r") as f:
    gj = json.load(f)

raw_coords = gj["features"][0]["geometry"]["coordinates"]   # [lon, lat]

# Convert to local XY (Z=0 for now)
centerline_2d = [latlon_to_xy(lat, lon) for lon, lat in raw_coords]

# Build 3-D points (Z will be filled by elevation interpolation later)
cl_pts = [Vector((x, y, 0.0)) for x, y in centerline_2d]

n_pts = len(cl_pts)
print(f"    Loaded {n_pts} centerline points")

# ─────────────────────────────────────────────────────────────────────────────
# 3. LOAD ELEVATION PROFILE & INTERPOLATE ALONG CENTERLINE
# ─────────────────────────────────────────────────────────────────────────────

print("[2/8] Loading elevation profile & interpolating …")

elev_refs = []
with open(ELEV_PATH, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        elev_refs.append({
            "lat": float(row["lat"]),
            "lon": float(row["lng"]),
            "elev_m": float(row["elevation_m"]),
            "desc": row["description"]
        })

# Convert elevation reference points to local XY
for e in elev_refs:
    e["x"], e["y"] = latlon_to_xy(e["lat"], e["lon"])

# Compute cumulative arc-length along the centerline
arc_len = [0.0]
for i in range(1, n_pts):
    d = (cl_pts[i] - cl_pts[i-1]).length
    arc_len.append(arc_len[-1] + d)
total_len = arc_len[-1]
print(f"    Centerline arc-length: {total_len:.1f} m")

# Map each elevation reference to the nearest centerline arc-length
# by finding the closest centerline point to each reference XY
def closest_arc_len(ref_x, ref_y):
    best_i, best_d = 0, 1e12
    for i, p in enumerate(cl_pts):
        d = math.hypot(p.x - ref_x, p.y - ref_y)
        if d < best_d:
            best_d, best_i = d, i
    return arc_len[best_i]

for e in elev_refs:
    e["s"] = closest_arc_len(e["x"], e["y"])

# Sort by arc-length
elev_refs.sort(key=lambda e: e["s"])

# Interpolate elevation at each centerline point
def interp_elev(s):
    if s <= elev_refs[0]["s"]:
        return elev_refs[0]["elev_m"]
    if s >= elev_refs[-1]["s"]:
        return elev_refs[-1]["elev_m"]
    for i in range(len(elev_refs)-1):
        s0, s1 = elev_refs[i]["s"], elev_refs[i+1]["s"]
        if s0 <= s <= s1:
            t = (s - s0) / max(s1 - s0, 1e-9)
            return elev_refs[i]["elev_m"] + t * (elev_refs[i+1]["elev_m"] - elev_refs[i]["elev_m"])
    return elev_refs[-1]["elev_m"]

# AC: Y=up convention → but Blender uses Z=up; we keep Z=up throughout
# Centre elevation (start/finish line) = 98.18m. We zero-reference to that.
BASE_ELEV = 98.18
for i, p in enumerate(cl_pts):
    raw_elev = interp_elev(arc_len[i])
    cl_pts[i].z = (raw_elev - BASE_ELEV) + TRACK_RAISE

print(f"    Elevation range: {min(p.z for p in cl_pts):.3f}m to {max(p.z for p in cl_pts):.3f}m (relative)")

# ─────────────────────────────────────────────────────────────────────────────
# 4. COMPUTE TANGENTS, NORMALS, CURVATURE → CORNER CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

print("[3/8] Computing curvature & classifying corners …")

def tangent_at(i):
    """Forward tangent unit vector at index i (2-D, ignores Z)."""
    if i == 0:
        d = cl_pts[1] - cl_pts[0]
    elif i == n_pts - 1:
        d = cl_pts[-1] - cl_pts[-2]
    else:
        d = cl_pts[i+1] - cl_pts[i-1]
    return normalise2(vec2(d.x, d.y))

def curvature_radius_at(i):
    """Menger curvature radius at index i using 3 consecutive points (2-D)."""
    if i == 0 or i == n_pts - 1:
        return 1e6  # straight
    A = vec2(cl_pts[i-1].x, cl_pts[i-1].y)
    B = vec2(cl_pts[i  ].x, cl_pts[i  ].y)
    C = vec2(cl_pts[i+1].x, cl_pts[i+1].y)
    ab = (B - A).length
    bc = (C - B).length
    ca = (A - C).length
    area2 = abs((B.x - A.x)*(C.y - A.y) - (C.x - A.x)*(B.y - A.y))
    if area2 < 1e-6:
        return 1e6
    denom = ab * bc * ca
    if denom < 1e-9:
        return 1e6
    return denom / (2.0 * area2)

# Store curvature radii
radii = [curvature_radius_at(i) for i in range(n_pts)]

# Detect corners: group consecutive points below a threshold into corner regions
CURVE_THRESHOLD = 80.0   # if radius < 80m, it's a corner region

in_corner = False
corner_start = 0
corners = []   # list of dicts: {start, end, min_radius, sign}

for i in range(n_pts):
    r = radii[i]
    entering = (r < CURVE_THRESHOLD)
    if entering and not in_corner:
        in_corner = True
        corner_start = i
    elif not entering and in_corner:
        in_corner = False
        # classify
        seg_radii = [radii[j] for j in range(corner_start, i)]
        min_r = min(seg_radii)
        apex_i = corner_start + seg_radii.index(min_r)
        # Sign: cross product tangent × next-tangent → positive=left, negative=right
        t0 = tangent_at(corner_start)
        t1 = tangent_at(i-1)
        cross_z = t0.x * t1.y - t0.y * t1.x
        sign = 1 if cross_z > 0 else -1   # +1=left turn, -1=right turn
        corners.append({
            "start": corner_start,
            "end":   i - 1,
            "apex":  apex_i,
            "min_r": min_r,
            "sign":  sign,
            "type":  "tight"   if min_r < CORNER_TIGHT_R  else
                     "medium"  if min_r < CORNER_MEDIUM_R else
                     "sweeper"
        })

if in_corner:
    seg_radii = [radii[j] for j in range(corner_start, n_pts)]
    min_r = min(seg_radii)
    apex_i = corner_start + seg_radii.index(min_r)
    t0 = tangent_at(corner_start)
    t1 = tangent_at(n_pts-1)
    cross_z = t0.x * t1.y - t0.y * t1.x
    sign = 1 if cross_z > 0 else -1
    corners.append({
        "start": corner_start,
        "end":   n_pts - 1,
        "apex":  apex_i,
        "min_r": min_r,
        "sign":  sign,
        "type":  "tight" if min_r < CORNER_TIGHT_R else
                 "medium" if min_r < CORNER_MEDIUM_R else
                 "sweeper"
    })

# Cap to 14 corners (if algo finds more, keep the 14 sharpest)
if len(corners) > 14:
    corners.sort(key=lambda c: c["min_r"])
    corners = corners[:14]
    corners.sort(key=lambda c: c["apex"])

print(f"    Found {len(corners)} corners:")
for idx, c in enumerate(corners):
    turn = "L" if c["sign"] == 1 else "R"
    print(f"      T{idx+1:02d} apex@pt{c['apex']:02d}  R={c['min_r']:5.1f}m  {c['type']:7s}  {turn}")

# ─────────────────────────────────────────────────────────────────────────────
# 5. SCENE SETUP
# ─────────────────────────────────────────────────────────────────────────────

print("[4/8] Setting up Blender scene …")

# Clear existing mesh objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False, confirm=False)

# ─────────────────────────────────────────────────────────────────────────────
# 6. MATERIALS
# ─────────────────────────────────────────────────────────────────────────────

def make_material(name, color_hex, roughness=0.85, metallic=0.0):
    """Create a Principled BSDF material with the given flat colour."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    r = int(color_hex[1:3], 16) / 255.0
    g = int(color_hex[3:5], 16) / 255.0
    b = int(color_hex[5:7], 16) / 255.0
    bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
    bsdf.inputs["Roughness"].default_value  = roughness
    bsdf.inputs["Metallic"].default_value   = metallic
    return mat

mat_asphalt  = make_material("road_asphalt",     "#1a1a1a", roughness=0.85)
mat_terrain  = make_material("grass_terrain",    "#3a7a2a", roughness=0.90)
mat_kerb_r   = make_material("kerb_red",         "#cc1111", roughness=0.70)
mat_kerb_w   = make_material("kerb_white",       "#eeeeee", roughness=0.70)
mat_barrier  = make_material("barrier_concrete", "#888888", roughness=0.80)
mat_pit      = make_material("pit_surface",      "#333333", roughness=0.88)

print("    Materials created.")

# ─────────────────────────────────────────────────────────────────────────────
# 7. BUILD TRACK SURFACE
# ─────────────────────────────────────────────────────────────────────────────

print("[5/8] Building track surface mesh …")

def build_track_surface():
    mesh = bpy.data.meshes.new("track_surface_mesh")
    obj  = bpy.data.objects.new("track_surface", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    left_verts  = []
    right_verts = []

    for i in range(n_pts):
        p  = cl_pts[i]
        t  = tangent_at(i)
        n  = normalise2(perp2(t))   # left-pointing normal

        # Elevate both edges at same Z as centreline (flat cross-section)
        z = p.z

        lv = bm.verts.new((p.x + n.x * HALF_WIDTH,
                            p.y + n.y * HALF_WIDTH,
                            z))
        rv = bm.verts.new((p.x - n.x * HALF_WIDTH,
                            p.y - n.y * HALF_WIDTH,
                            z))
        left_verts.append(lv)
        right_verts.append(rv)

    bm.verts.ensure_lookup_table()

    # Build quad faces
    for i in range(n_pts - 1):
        l0, r0 = left_verts[i],   right_verts[i]
        l1, r1 = left_verts[i+1], right_verts[i+1]
        bm.faces.new([l0, r0, r1, l1])

    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    mesh.shade_flat()
    obj.data.materials.append(mat_asphalt)
    print(f"    Track surface: {n_pts-1} quads built.")
    return obj, left_verts, right_verts

track_obj, left_edge_verts, right_edge_verts = build_track_surface()

# Store edge positions for barrier/kerb placement (world-space tuples)
left_edge  = []
right_edge = []
for i in range(n_pts):
    t = tangent_at(i)
    n = normalise2(perp2(t))
    p = cl_pts[i]
    z = p.z
    left_edge.append( Vector((p.x + n.x * HALF_WIDTH, p.y + n.y * HALF_WIDTH, z)) )
    right_edge.append(Vector((p.x - n.x * HALF_WIDTH, p.y - n.y * HALF_WIDTH, z)) )

# ─────────────────────────────────────────────────────────────────────────────
# 8. BUILD TERRAIN
# ─────────────────────────────────────────────────────────────────────────────

print("[6/8] Building terrain …")

def build_terrain():
    mesh = bpy.data.meshes.new("terrain_mesh")
    obj  = bpy.data.objects.new("terrain", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    half = TERRAIN_SIZE / 2.0
    step = TERRAIN_SIZE / TERRAIN_GRID

    # Build grid vertices with elevation
    verts = []
    for row in range(TERRAIN_GRID + 1):
        row_verts = []
        for col in range(TERRAIN_GRID + 1):
            wx = -half + col * step
            wy = -half + row * step
            # Find closest centerline point for elevation reference
            best_s = arc_len[0]
            best_d = 1e12
            for idx, cp in enumerate(cl_pts):
                d = math.hypot(cp.x - wx, cp.y - wy)
                if d < best_d:
                    best_d = d
                    best_s = arc_len[idx]
            raw_e = interp_elev(best_s)
            # Blend: close to track → use track elev; far away → flatten gently
            dist_factor = min(best_d / 30.0, 1.0)
            terrain_e = raw_e - BASE_ELEV  # same reference as track
            wz = terrain_e * (1.0 - dist_factor * 0.3)   # slight smoothing away from track
            row_verts.append(bm.verts.new((wx, wy, wz)))
        verts.append(row_verts)

    bm.verts.ensure_lookup_table()

    for row in range(TERRAIN_GRID):
        for col in range(TERRAIN_GRID):
            v0 = verts[row    ][col    ]
            v1 = verts[row    ][col + 1]
            v2 = verts[row + 1][col + 1]
            v3 = verts[row + 1][col    ]
            bm.faces.new([v0, v1, v2, v3])

    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    mesh.shade_smooth()
    obj.data.materials.append(mat_terrain)
    print(f"    Terrain: {TERRAIN_GRID}×{TERRAIN_GRID} grid built.")
    return obj

terrain_obj = build_terrain()

# ─────────────────────────────────────────────────────────────────────────────
# 9. BUILD PERMANENT EDGE KERBS
# ─────────────────────────────────────────────────────────────────────────────
# These are permanent kerbs running along each corner's inside and outside edge.
# NOT portable barriers. No layout-defining elements.
# Inside (apex): raised 3cm, 30cm wide, alternating red/white stripes
# Outside (exit): near-flush 0.5cm, 20cm wide, alternating red/white stripes

print("[7/8] Building permanent edge kerbs …")

kerb_objects = []

def build_kerb_strip(pts_inner, pts_outer, n_segs, raise_h, mat_list, name):
    """
    Build an alternating red/white kerb strip.
    pts_inner / pts_outer: list of Vector positions for the two longitudinal edges.
    n_segs: number of alternating colour segments.
    raise_h: extra Z raise for the kerb surface.
    mat_list: [mat_red, mat_white] or [mat_white, mat_red]
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj  = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    mesh.materials.append(mat_kerb_r)
    mesh.materials.append(mat_kerb_w)

    bm = bmesh.new()
    n  = len(pts_inner)
    if n < 2:
        bm.free()
        return obj

    all_inner = []
    all_outer = []
    for i, (pi, po) in enumerate(zip(pts_inner, pts_outer)):
        vi = bm.verts.new((pi.x, pi.y, pi.z + raise_h))
        vo = bm.verts.new((po.x, po.y, po.z + raise_h))
        all_inner.append(vi)
        all_outer.append(vo)

    bm.verts.ensure_lookup_table()

    seg_size = max(1, n // n_segs)
    for i in range(n - 1):
        seg_idx = i // seg_size
        mat_idx = seg_idx % 2   # 0=red, 1=white
        face = bm.faces.new([all_inner[i], all_outer[i],
                              all_outer[i+1], all_inner[i+1]])
        face.material_index = mat_idx

    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.shade_flat()
    kerb_objects.append(obj)
    return obj


for cidx, corner in enumerate(corners):
    s  = corner["start"]
    e  = corner["end"]
    ap = corner["apex"]
    sg = corner["sign"]    # +1=left, +right=-1
    ct = corner["type"]
    t_num = cidx + 1

    # Span the kerb over the middle portion of the corner (apex ± spread)
    spread = {
        "tight":   max(2, (e - s) // 2),
        "medium":  max(2, (e - s) // 3),
        "sweeper": max(1, (e - s) // 4),
    }[ct]

    ks = max(s, ap - spread)
    ke = min(e, ap + spread) + 1

    # Collect edge positions for this corner span
    inside_inner  = []
    inside_outer  = []
    outside_inner = []
    outside_outer = []

    for i in range(ks, ke):
        t = tangent_at(i)
        n = normalise2(perp2(t))
        p = cl_pts[i]
        z = p.z

        # Inside of this corner = the apex side
        # sign +1 (left turn) → left edge (n-direction) is inside
        # sign -1 (right turn) → right edge (-n-direction) is inside
        if sg == 1:
            # Left turn: inside = left edge
            edge_inside  = Vector((p.x + n.x * HALF_WIDTH,         p.y + n.y * HALF_WIDTH,         z))
            edge_outside = Vector((p.x - n.x * HALF_WIDTH,         p.y - n.y * HALF_WIDTH,         z))
        else:
            # Right turn: inside = right edge
            edge_inside  = Vector((p.x - n.x * HALF_WIDTH,         p.y - n.y * HALF_WIDTH,         z))
            edge_outside = Vector((p.x + n.x * HALF_WIDTH,         p.y + n.y * HALF_WIDTH,         z))

        # Inside kerb: from track-edge outward by KERB_INNER_WIDTH
        if sg == 1:
            kerb_i_outer = Vector((p.x + n.x * (HALF_WIDTH + KERB_INNER_WIDTH),
                                   p.y + n.y * (HALF_WIDTH + KERB_INNER_WIDTH), z))
        else:
            kerb_i_outer = Vector((p.x - n.x * (HALF_WIDTH + KERB_INNER_WIDTH),
                                   p.y - n.y * (HALF_WIDTH + KERB_INNER_WIDTH), z))

        # Outside exit kerb: beyond the outside edge
        if sg == 1:
            kerb_o_outer = Vector((p.x - n.x * (HALF_WIDTH + KERB_OUTER_WIDTH),
                                   p.y - n.y * (HALF_WIDTH + KERB_OUTER_WIDTH), z))
        else:
            kerb_o_outer = Vector((p.x + n.x * (HALF_WIDTH + KERB_OUTER_WIDTH),
                                   p.y + n.y * (HALF_WIDTH + KERB_OUTER_WIDTH), z))

        inside_inner.append(edge_inside)
        inside_outer.append(kerb_i_outer)
        outside_inner.append(edge_outside)
        outside_outer.append(kerb_o_outer)

    if len(inside_inner) < 2:
        continue

    # Inside apex kerb (raised)
    build_kerb_strip(inside_inner, inside_outer,
                     KERB_SEGS, KERB_INNER_RAISE,
                     [mat_kerb_r, mat_kerb_w],
                     f"kerb_T{t_num:02d}_inside")

    # Outside exit kerb (nearly flush)
    build_kerb_strip(outside_inner, outside_outer,
                     KERB_SEGS, KERB_OUTER_RAISE,
                     [mat_kerb_r, mat_kerb_w],
                     f"kerb_T{t_num:02d}_outside")

    kerb_type_label = {"tight": "raised 3cm alternating", "medium": "standard alternating", "sweeper": "flat sausage-style"}[ct]
    turn_dir = "Left" if sg == 1 else "Right"
    print(f"    T{t_num:02d} {turn_dir} {ct:7s}  R={corner['min_r']:5.1f}m  apex@pt{ap:02d}  kerb={kerb_type_label}")

print(f"    Total kerb objects: {len(kerb_objects)}")

# ─────────────────────────────────────────────────────────────────────────────
# 10. BUILD PERMANENT CONCRETE / ARMCO OUTER BOUNDARY BARRIERS
# ─────────────────────────────────────────────────────────────────────────────
# These run the FULL length of both track edges at BARRIER_OFFSET beyond the edge.
# Lower half = concrete block (0.5m), upper half = tyre wall (0.5m).
# NO portable chicanes, NO layout redirectors — permanent boundary only.

print("[8/8] Building permanent outer boundary barriers …")

barrier_objects = []

def build_barrier_wall(edge_pts, side_name):
    """
    Extrudes a wall of height BARRIER_CONCRETE_H + BARRIER_TIRE_H
    along the given edge positions, offset outward by BARRIER_OFFSET.
    Two materials: lower = barrier_concrete, upper drawn using same mat.
    """
    mesh = bpy.data.meshes.new(f"barriers_{side_name}_mesh")
    obj  = bpy.data.objects.new(f"barriers_{side_name}", mesh)
    bpy.context.collection.objects.link(obj)

    mesh.materials.append(mat_barrier)

    bm = bmesh.new()
    total_h = BARRIER_CONCRETE_H + BARRIER_TIRE_H

    n = len(edge_pts)
    bottom_verts = []
    top_verts    = []

    for i in range(n):
        p  = edge_pts[i]
        t  = tangent_at(i)
        nv = normalise2(perp2(t))

        # Outward direction depends on which side
        if side_name == "left":
            ox, oy = nv.x, nv.y
        else:
            ox, oy = -nv.x, -nv.y

        bx = p.x + ox * BARRIER_OFFSET
        by = p.y + oy * BARRIER_OFFSET
        bz = p.z

        bv = bm.verts.new((bx, by, bz))
        tv = bm.verts.new((bx, by, bz + total_h))
        bottom_verts.append(bv)
        top_verts.append(tv)

    bm.verts.ensure_lookup_table()

    for i in range(n - 1):
        b0, b1 = bottom_verts[i], bottom_verts[i+1]
        t0, t1 = top_verts[i],    top_verts[i+1]
        face = bm.faces.new([b0, b1, t1, t0])
        face.material_index = 0

    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.shade_flat()
    barrier_objects.append(obj)
    print(f"    Barrier wall '{side_name}': {n-1} panels")
    return obj

build_barrier_wall(left_edge,  "left")
build_barrier_wall(right_edge, "right")

# ─────────────────────────────────────────────────────────────────────────────
# 11. JOIN BY EXPORT GROUP & EXPORT FBX
# ─────────────────────────────────────────────────────────────────────────────

print("\n[Export] Exporting FBX files …")

def export_objects(objs, filepath):
    """Deselect all, select given objects, export FBX."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        if o and o.name in bpy.data.objects:
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
    bpy.ops.export_scene.fbx(
        filepath         = filepath,
        use_selection    = True,
        global_scale     = 1.0,
        axis_forward     = '-Z',
        axis_up          = 'Y',
        apply_unit_scale = True,
        apply_scale_options = 'FBX_SCALE_NONE',
        bake_space_transform = True,
        mesh_smooth_type = 'FACE',
        use_mesh_modifiers = True,
        use_tspace       = True,
        use_armature_deform_only = False,
        add_leaf_bones   = False,
        path_mode        = 'COPY',
        embed_textures   = False,
    )
    print(f"    → {filepath}")

# Master all-in-one
all_objects = [track_obj, terrain_obj] + kerb_objects + barrier_objects
export_objects(all_objects, os.path.join(OUTPUT_DIR, "track_mesh.fbx"))

# Individual groups
export_objects([track_obj],      os.path.join(OUTPUT_DIR, "track_surface.fbx"))
export_objects([terrain_obj],    os.path.join(OUTPUT_DIR, "terrain.fbx"))
export_objects(kerb_objects,     os.path.join(OUTPUT_DIR, "curbs.fbx"))
export_objects(barrier_objects,  os.path.join(OUTPUT_DIR, "barriers.fbx"))

print("\n✅ All FBX files exported to:", OUTPUT_DIR)

# ─────────────────────────────────────────────────────────────────────────────
# 12. FINAL SUMMARY PRINT
# ─────────────────────────────────────────────────────────────────────────────

print("\n═══════════════════════════════════════════════════════")
print("  Stockholm Karting Center — Mesh Build Complete")
print("═══════════════════════════════════════════════════════")
print(f"  Centerline points : {n_pts}")
print(f"  Track length      : {total_len:.1f} m")
print(f"  Track width       : {TRACK_WIDTH} m")
print(f"  Corners found     : {len(corners)}")
print(f"  Kerb objects      : {len(kerb_objects)}")
print(f"  Barrier panels    : {sum(len(bpy.data.objects[o.name].data.polygons) for o in barrier_objects)}")
print(f"  Terrain grid      : {TERRAIN_GRID}×{TERRAIN_GRID}")
print(f"  Output dir        : {OUTPUT_DIR}")
print("═══════════════════════════════════════════════════════")
print("\nCorner Map:")
for cidx, corner in enumerate(corners):
    ct  = corner["type"]
    sg  = corner["sign"]
    t_num = cidx + 1
    dir_s = "L" if sg == 1 else "R"
    kerb_desc = {
        "tight":   "raised 3cm alternating red/white",
        "medium":  "standard alternating red/white",
        "sweeper": "flat near-flush red/white",
    }[ct]
    print(f"  T{t_num:02d} ({dir_s}) R={corner['min_r']:5.1f}m  [{ct:7s}]  → {kerb_desc}")
print("\nDone. Open Blender to inspect before compiling to .kn5.")
