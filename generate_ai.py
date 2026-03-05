"""
Stockholm Karting Center — Assetto Corsa AI Line Generator
Generates fast_lane.ai and pit_lane.ai from track_centerline.geojson

Run this script to regenerate the AI line after track centerline updates.

USAGE:
  python3 generate_ai.py

Output:
  content/tracks/stockholm_karting/ai/fast_lane.ai
  content/tracks/stockholm_karting/ai/pit_lane.ai

AC .ai file format:
  Header: b'AI\\x00\\x00' + count (uint32 LE)
  Per point: x, y, z, speed_hint, side_left, side_right (all float32 LE)
  x/z = horizontal track coords in meters
  y   = elevation (meters above track datum)
  speed_hint = m/s (AC uses as starting estimate, overridden by spline solver)
  side_l/r = track half-widths in meters
"""
import struct, math, json, os

# ── Real elevation offsets from USGS sampling (meters above start/finish) ─
# Start/Finish = 98.18m ASL → baseline 0.0
ELEV_OFFSETS = {
    0:  0.00,  # Start/Finish            98.18m
    7:  -1.01, # Turn 1 Entry            97.17m  ← first elevation change starts
    8:  -1.89, # Turn 1 Apex             96.29m
    9:  -1.98, # Turn 1 Exit             96.20m
    10: -2.46, # Back Straight Start     95.72m  ← lowest point
    11: -0.79, # Mid Back Straight       97.39m  ← climbing back up
    12: -0.56, # Hairpin Entry           97.62m
    13: -0.14, # Hairpin Apex            98.04m
    14: -0.54, # Hairpin Exit            97.64m
    15:  0.09, # Infield Section         98.27m  ← highest point
}

# Speed hints per track section (km/h → m/s conversion happens below)
# These are starting estimates — AC's AI solver will optimise further
SPEED_HINTS = {
    'sf_straight':   70,  # Start/Finish straight
    'turn1_complex': 45,  # Turn 1 (banked sweeper)
    'back_straight': 65,  # Back straight (uphill)
    'hairpin':       30,  # Hairpin (tight left)
    'infield':       55,  # Infield sweepers (downhill)
    'chicane':       50,  # Final chicane
}

def get_speed(idx, total):
    """Return speed hint in m/s based on track section."""
    if   idx < 7:       return SPEED_HINTS['sf_straight']   / 3.6
    elif idx < 15:      return SPEED_HINTS['turn1_complex']  / 3.6
    elif idx < 21:      return SPEED_HINTS['back_straight']  / 3.6
    elif idx < 31:      return SPEED_HINTS['hairpin']        / 3.6
    elif idx < 37:      return SPEED_HINTS['infield']        / 3.6
    else:               return SPEED_HINTS['chicane']        / 3.6


def write_ai_file(filename, points):
    """Write binary .ai file."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'wb') as f:
        f.write(b'AI\x00\x00')
        f.write(struct.pack('<I', len(points)))
        for x, y, z, speed, side_l, side_r in points:
            f.write(struct.pack('<ffffff', x, y, z, speed, side_l, side_r))
    print(f"✅ Wrote {filename}: {len(points)} points")


def main():
    geojson_path = 'track_centerline.geojson'
    if not os.path.exists(geojson_path):
        print(f"ERROR: {geojson_path} not found. Run from stockholm-kart-ac/ root.")
        return

    with open(geojson_path) as f:
        gj = json.load(f)

    coords = gj['features'][0]['geometry']['coordinates']
    center_lat = 45.0772
    center_lng = -94.1858
    m_per_deg_lat = 111320
    m_per_deg_lng = 111320 * math.cos(math.radians(center_lat))

    ai_points = []
    for i, (lng, lat) in enumerate(coords[:-1]):  # skip closing duplicate
        x = (lng - center_lng) * m_per_deg_lng
        z = (lat - center_lat) * m_per_deg_lat
        y = ELEV_OFFSETS.get(i, 0.0)
        speed = get_speed(i, len(coords))
        ai_points.append((x, y, z, speed, 3.5, 3.5))

    base = 'content/tracks/stockholm_karting/ai'
    write_ai_file(f'{base}/fast_lane.ai', ai_points)
    write_ai_file(f'{base}/pit_lane.ai', ai_points[:12])
    print(f"\nTrack: {len(ai_points)} waypoints, "
          f"est. {sum(math.sqrt((ai_points[i][0]-ai_points[i-1][0])**2 + (ai_points[i][2]-ai_points[i-1][2])**2) for i in range(1,len(ai_points))):.0f}m")


if __name__ == '__main__':
    main()
