# 3D Models — Stockholm Karting Center

## This folder holds the 3D track mesh files

### Required files (generate in Blender or Race Track Builder):

| File | Description |
|------|-------------|
| `stockholm_karting.kn5` | Main compiled track model (AC format) |
| `track_surface.fbx` | Pre-export Blender mesh |
| `barriers.fbx` | Tire walls, concrete barriers |
| `terrain.fbx` | Ground/grass mesh |
| `pit_building.fbx` | Pit lane structure |
| `start_finish_gantry.fbx` | Start/finish overhead structure |

### Workflow:

1. **Race Track Builder (easiest):**
   - Import `../../../track_centerline.geojson`
   - Load `../heightmap.png` as terrain DEM
   - Set track width: 8m
   - Add banked turns at T1 and final complex
   - Export → Assetto Corsa

2. **Blender:**
   - Install BlenderGIS plugin
   - Import centerline GeoJSON as path
   - Apply heightmap.png as terrain displacement
   - Model 8m-wide track surface along path
   - Install ksEditor/KN5 exporter
   - Export → .kn5

### Real data upgrades:
- Replace heightmap.png with drone DEM for 1cm accuracy
- Import GPS lap data for exact racing line
- Use Google Earth satellite imagery as texture reference

### AC mesh requirements:
- Object named `ROAD` for tarmac surfaces (AC physics detection)
- Objects named `GRASS`, `GRAVEL`, `KERB` for surface physics
- Pit lane object named `PITLANE`
- Start position markers matching track.ini coordinates
