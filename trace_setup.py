"""
Stockholm Karting Center — Step 1: Trace Setup
===============================================
Run this script INSIDE Blender (not --background):
  1. Open Blender
  2. Go to the Scripting workspace (top tab bar)
  3. Open this file
  4. Press Run Script (▶)

This will:
  - Load satellite_clear.png as a background image in the 3D viewport
  - Create an editable Bezier curve for you to trace the track
  - Scale the satellite image to real-world meters (~420m wide)

After running:
  - Press Numpad 7 for top-down view
  - Press Tab to enter Edit Mode on the curve
  - Move/add/delete Bezier points to trace the track centerline
  - The image is your reference — trace the CENTERLINE (middle of the track)
  - When done, run build_from_curve.py to generate the full mesh + export FBX
"""

import bpy
import os
import math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAT_PATH   = os.path.join(SCRIPT_DIR, "satellite_clear.png")

# ── CLEAR SCENE ───────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ── LOAD SATELLITE IMAGE ──────────────────────────────────────────────────────
if not os.path.exists(SAT_PATH):
    raise FileNotFoundError(f"Satellite image not found: {SAT_PATH}\nRe-download from GitHub.")

sat_img = bpy.data.images.load(SAT_PATH)

# Create an Image Empty — shows the satellite image in the viewport
bpy.ops.object.empty_add(type='IMAGE', location=(0, 0, -0.1))
empty = bpy.context.active_object
empty.name = "satellite_background"
empty.data = sat_img

# Scale: satellite_clear.png is 874x973 pixels
# Google Maps zoom ~18 at 45°N ≈ 0.42m/px → image covers ~367m x 409m
# We'll use 380m as the width scale
IMG_W_PX = 874
IMG_H_PX = 973
METERS_PER_PX = 0.43   # approx for zoom 18 at 45°N
img_w_m = IMG_W_PX * METERS_PER_PX   # ~376m
img_h_m = IMG_H_PX * METERS_PER_Px  if False else IMG_H_PX * METERS_PER_PX  # ~418m

# Image Empty scale: Blender uses uniform scale for image empties
# Set X scale = image width in meters, Y = height
empty.empty_display_size = 1.0
empty.scale = (img_w_m / 2, img_h_m / 2, 1.0)

print(f"Satellite image loaded: {img_w_m:.0f}m x {img_h_m:.0f}m")
print(f"  (If track looks wrong size, adjust empty.scale in the outliner)")

# ── CREATE INITIAL BEZIER CURVE ───────────────────────────────────────────────
# Rough initial shape — Spencer will edit this to match the satellite
# Clockwise, front straight at NORTH (Y=0, top of image area)
# Track extends south

INIT_WAYPOINTS = [
    # Front straight (north edge, W→E)
    (-100,  50),
    (   0,  50),
    ( 100,  50),
    # NE corner heading south
    ( 140,  20),
    ( 150, -30),
    # East side + oval section
    ( 140, -80),
    ( 100,-150),
    (  30,-180),
    ( -30,-160),
    ( -60,-120),
    # S-bends heading northwest
    ( -40, -70),
    (  10, -50),
    ( -20, -20),
    # NW complex
    ( -80, -10),
    (-130,   5),
    (-100,  50),  # close to start
]

curve_data = bpy.data.curves.new("track_centerline", type='CURVE')
curve_data.dimensions = '3D'
curve_data.resolution_u = 12

spline = curve_data.splines.new('BEZIER')
spline.bezier_points.add(len(INIT_WAYPOINTS) - 1)
spline.use_cyclic_u = False  # first == last, so not cyclic

for i, (x, y) in enumerate(INIT_WAYPOINTS):
    bp = spline.bezier_points[i]
    bp.co = (x, y, 0)
    bp.handle_left_type  = 'AUTO'
    bp.handle_right_type = 'AUTO'

curve_obj = bpy.data.objects.new("track_centerline", curve_data)
bpy.context.scene.collection.objects.link(curve_obj)

# Select the curve so Spencer can immediately edit it
bpy.ops.object.select_all(action='DESELECT')
curve_obj.select_set(True)
bpy.context.view_layer.objects.active = curve_obj

# Set viewport to top-down
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.region_3d.view_perspective = 'ORTHO'
                # Set view to top (numpad 7 equivalent)
                import mathutils
                space.region_3d.view_rotation = mathutils.Quaternion((1, 0, 0, 0))
                space.region_3d.view_distance = 400
                space.region_3d.view_location = (0, -50, 0)
                # Show background image
                space.show_region_toolbar = True
                break

print("""
╔════════════════════════════════════════════════════════════╗
║  TRACE SETUP COMPLETE                                      ║
╠════════════════════════════════════════════════════════════╣
║  1. Press NUMPAD 7 for top-down view (if not already)     ║
║  2. You should see the satellite image as background       ║
║  3. The orange curve = initial track shape (rough)         ║
║  4. Press TAB to enter Edit Mode                          ║
║  5. Move Bezier points to trace the CENTERLINE of track   ║
║     - G = grab/move point                                 ║
║     - E = extrude new point                               ║
║     - CTRL+click = add point on curve                     ║
║     - Alt+drag handles for smooth curves                  ║
║  6. When done, go back to Object Mode (TAB)               ║
║  7. Run build_from_curve.py to generate the full mesh     ║
╚════════════════════════════════════════════════════════════╝
""")
