"""
Stockholm Karting Center — Assetto Corsa Heightmap Generator
Uses USGS Elevation Point Query Service to sample real terrain elevation.
Output: heightmap.png suitable for AC track terrain

USAGE:
  pip install Pillow numpy
  python3 heightmap_gen.py

  # With drone DEM input (future):
  python3 heightmap_gen.py --input drone_dem.tif

The output heightmap.png goes in:
  content/tracks/stockholm_karting/heightmap.png

AC heightmap specs:
  - Grayscale PNG, White (255) = highest, Black (0) = lowest
  - Typical: 512x512 or 1024x1024
  - Must match [TERRAIN] SIZE settings in track.ini
"""
import time, json, urllib.request, sys

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("Install: pip install Pillow numpy")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────
CENTER_LAT = 45.0772
CENTER_LNG = -94.1858
SPAN_LAT   = 0.006   # ~670m N-S coverage
SPAN_LNG   = 0.010   # ~790m E-W coverage
GRID_SIZE  = 16      # 16x16 = 256 API calls (use 8 for speed test)
OUTPUT_SIZE = 512    # Output PNG resolution
OUTPUT_PATH = 'content/tracks/stockholm_karting/heightmap.png'


def get_elevation(lat, lng):
    """Fetch real elevation from USGS Elevation Point Query Service."""
    url = (f"https://epqs.nationalmap.gov/v1/json"
           f"?x={lng}&y={lat}&wkid=4326&includeDate=false")
    req = urllib.request.Request(url, headers={'User-Agent': 'ACTrackBuilder/1.0'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return float(json.load(r).get('value', 322)) * 0.3048  # ft → meters


def generate_from_usgs(grid_size=GRID_SIZE, output_size=OUTPUT_SIZE):
    """Sample USGS grid and generate heightmap.png."""
    print(f"Sampling {grid_size}x{grid_size} USGS elevation grid "
          f"({grid_size*grid_size} API calls, ~{grid_size*grid_size*0.35:.0f}s)...")

    grid = []
    for row in range(grid_size):
        r = []
        lat = CENTER_LAT + SPAN_LAT/2 - row * (SPAN_LAT / (grid_size-1))
        for col in range(grid_size):
            lng = CENTER_LNG - SPAN_LNG/2 + col * (SPAN_LNG / (grid_size-1))
            try:
                elev = get_elevation(lat, lng)
                r.append(elev)
                print(f"  [{row:02d},{col:02d}] {lat:.4f},{lng:.4f} → {elev:.2f}m")
            except Exception as e:
                print(f"  [{row:02d},{col:02d}] ERROR: {e} → fallback 98.0m")
                r.append(98.0)
            time.sleep(0.35)
        grid.append(r)

    return _save_heightmap(grid, output_size)


def generate_from_tif(tif_path, output_size=OUTPUT_SIZE):
    """Convert drone DEM GeoTIFF to AC heightmap (requires rasterio)."""
    try:
        import rasterio
        from rasterio.enums import Resampling
    except ImportError:
        print("Install: pip install rasterio")
        return

    with rasterio.open(tif_path) as src:
        data = src.read(1, out_shape=(output_size, output_size),
                        resampling=Resampling.bilinear)
    return _save_heightmap(data.tolist(), output_size, already_array=True)


def _save_heightmap(grid, output_size, already_array=False):
    arr = np.array(grid) if not already_array else grid
    min_e, max_e = arr.min(), arr.max()
    print(f"\nElevation: {min_e:.2f}m – {max_e:.2f}m  (relief: {max_e-min_e:.2f}m)")

    if max_e > min_e:
        normalized = ((arr - min_e) / (max_e - min_e) * 255).astype(np.uint8)
    else:
        normalized = np.full_like(arr, 128, dtype=np.uint8)

    img_small = Image.fromarray(normalized, mode='L')
    img = img_small.resize((output_size, output_size), Image.BILINEAR)
    img.save(OUTPUT_PATH)
    print(f"✅ Saved {OUTPUT_PATH} ({output_size}x{output_size})")
    return min_e, max_e


if __name__ == '__main__':
    if '--input' in sys.argv:
        idx = sys.argv.index('--input')
        tif_path = sys.argv[idx + 1]
        print(f"Using drone DEM: {tif_path}")
        generate_from_tif(tif_path)
    else:
        generate_from_usgs()
