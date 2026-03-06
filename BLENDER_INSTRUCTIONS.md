# Stockholm Karting Center — Blender → Assetto Corsa Pipeline

**Track:** Stockholm Karting Center, Cokato MN  
**Script:** `build_track_mesh.py`  
**Output:** `content/tracks/stockholm_karting/models/`

---

## Prerequisites

| Tool | Version | Download |
|---|---|---|
| Blender | 3.6 LTS or 4.x | https://www.blender.org/download/ |
| Assetto Corsa SDK (ksEditor) | Latest | Included with AC (Steam → Tools) |
| Python (bundled in Blender) | 3.10+ | Comes with Blender |

---

## Step 1 — Run the Script in Blender (Background Mode, Fastest)

Open **Windows Command Prompt** or **PowerShell** and run:

```bat
"C:\Program Files\Blender Foundation\Blender 4.x\blender.exe" ^
  --background ^
  --python "C:\path\to\stockholm-kart-ac\build_track_mesh.py"
```

**Replace the path** with your actual Blender install directory and workspace path.

Watch the console output — the script prints progress for every step:
```
[1/8] Loading GeoJSON centerline …
[2/8] Loading elevation profile & interpolating …
[3/8] Computing curvature & classifying corners …
[4/8] Setting up Blender scene …
[5/8] Building track surface mesh …
[6/8] Building terrain …
[7/8] Building permanent edge kerbs …
[8/8] Building permanent outer boundary barriers …
[Export] Exporting FBX files …
✅ All FBX files exported
```

Total runtime: ~30–60 seconds depending on machine.

---

## Step 2 — Inspect in Blender GUI (Optional but Recommended)

If you want to visually inspect before compiling:

1. Open Blender normally
2. Go to **Scripting** workspace (top tab bar)
3. Click **Open** → select `build_track_mesh.py`
4. Click **▶ Run Script** (or press `Alt+P`)
5. Switch to **Layout** workspace to view the 3D scene
6. Use **numpad 5** for orthographic view, **numpad 7** for top-down

**What you should see:**
- Dark grey asphalt strip looping around the track (~1km long)
- Green terrain ground plane (200m × 200m)
- Red/white kerb strips at each corner apex
- Grey concrete barrier walls along both edges

---

## Step 3 — Fix Any Issues in Blender

### If track looks twisted or flipped normals:
1. Select `track_surface` object
2. Tab → Edit Mode
3. `A` to select all
4. `Alt+N` → **Recalculate Outside**
5. Tab back to Object Mode

### If terrain Z-fighting with track:
The track is raised 5cm (TRACK_RAISE = 0.05) above terrain. If you still see flickering:
1. Select terrain object
2. In Material Properties → set Z Offset = -0.01 (Blender preview only)

### If scale looks wrong:
The script outputs in metres. Verify: select `track_surface` → press `N` for side panel → check Dimensions. Should be approximately:
- X: ~270m  
- Y: ~200m  
- Z: ~2.5m (elevation relief)

---

## Step 4 — Open ksEditor and Import FBX

ksEditor is in your Steam folder:  
`C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\sdk\editor\`

### Launch:
Double-click `ksEditor.exe`

### Import the mesh:
1. **File → Open** → navigate to:  
   `content/tracks/stockholm_karting/models/track_mesh.fbx`
2. The scene loads. You should see the track layout in the viewport.
3. Verify object list on the left shows:
   - `track_surface`
   - `terrain`
   - `barriers_left`, `barriers_right`
   - `kerb_T01_inside` through `kerb_T14_inside` (and `_outside` variants)

---

## Step 5 — Assign AC Physics Surfaces in ksEditor

After import, each object needs a surface physics tag:

| Object | AC Surface Tag |
|---|---|
| `track_surface` | `road_asphalt` |
| `terrain` | `grass_terrain` |
| `kerb_*` | `kerb_red` or `kerb_white` |
| `barriers_*` | `barrier_concrete` |

**How to assign:**
1. Select object in viewport
2. Right-click → **Properties**
3. In **Custom Properties**, add:  
   Key: `SURFACE`  Value: `road_asphalt` (etc.)

---

## Step 6 — Compile to .kn5

1. In ksEditor: **File → Save** → saves `.kseditor` project file
2. **File → Pack** (or **Build → Build Track**)
3. Choose output: `content/tracks/stockholm_karting/`
4. Click **Build**

The compiler creates:
```
content/tracks/stockholm_karting/stockholm_karting.kn5
```

---

## Step 7 — Test in Assetto Corsa

1. Copy the entire `stockholm_karting/` folder to:  
   `C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\content\tracks\`
2. Launch Assetto Corsa
3. Go to **Single Player → Practice**
4. Select **Stockholm Karting Center** from the track list
5. Pick any kart and go

---

## File Map

```
stockholm-kart-ac/
├── build_track_mesh.py          ← This script
├── track_centerline.geojson     ← GPS centerline (46 points)
├── elevation_profile.csv        ← Elevation reference data
├── BLENDER_INSTRUCTIONS.md      ← This file
└── content/tracks/stockholm_karting/
    ├── track.ini
    ├── surfaces.ini
    ├── heightmap.png
    ├── ai/                       ← AI line data
    ├── data/
    ├── ui/
    └── models/
        ├── track_mesh.fbx        ← All-in-one export
        ├── track_surface.fbx     ← Asphalt only
        ├── terrain.fbx           ← Ground plane only
        ├── curbs.fbx             ← All kerb objects
        └── barriers.fbx          ← Outer barriers only
```

---

## Common Errors & Fixes

### `ModuleNotFoundError: No module named 'bpy'`
You're running the script with system Python, not Blender's Python.  
**Fix:** Always run via `blender --background --python script.py`

### `FileNotFoundError: track_centerline.geojson`
The script uses `__file__` to find the GeoJSON relative to itself.  
**Fix:** Make sure the script and .geojson are in the same directory (`stockholm-kart-ac/`).

### Blender opens a GUI window instead of running headless
You're missing the `--background` flag.  
**Fix:** Add `--background` right after `blender.exe` in the command.

### FBX export fails with `RuntimeError: Operator bpy.ops.export_scene.fbx`
The FBX export add-on isn't enabled.  
**Fix:** Open Blender GUI → Edit → Preferences → Add-ons → search "FBX" → enable **Import-Export: FBX format**. Then re-run.

### Track appears underground in AC
The elevation offset might mismatch with `track.ini` START_POSITION.  
**Fix:** In Blender, select `track_surface`, note the Z at the start/finish point. Update `track.ini` → `START_POSITION_0` Z value to match.

### ksEditor won't open FBX
Try exporting from Blender as `.obj` instead:  
In the script, change the export calls to use:  
`bpy.ops.export_scene.obj(filepath=..., use_selection=True, axis_up='Y', axis_forward='-Z')`

### Kerbs look inside-out / wrong side
Turn direction detection may be inverted for specific corners.  
**Fix:** In Blender, select the offending kerb, Tab → Edit Mode, `A`, `Alt+N` → Flip.

---

## Layout Variants Note

Stockholm Karting has 4 layout configurations using **portable tire barriers**.  
These are **not** included in this mesh — the full clean track surface is built.

To add layout variants:
1. In AC, create separate `layout_*` folders under `stockholm_karting/`
2. Place portable objects (tire stacks etc.) as separate `.kn5` objects in each layout
3. Reference them in each layout's `track.ini`

Jeff handles this manually. The base mesh stays clean.

---

*Generated by Highlands (TopDog AI) — 2026-03-06*
