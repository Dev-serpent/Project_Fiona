# Vsee

Vsee is Fiona's current holography software layer. It is a point/edge 3D wireframe viewer, not true optical holography yet.

## Open The App

```bash
python3 -m fiona.cli vsee
```

With specific input files:

```bash
python3 -m fiona.cli vsee --points ./points.csv --edges ./edges.csv
```

The Vsee process is a foreground GUI app and stays open until the window is closed.

## Data Model

Points are rows with an id and 3D coordinates:

```csv
id,x,y,z
A,-1,-1,-1
B,1,-1,-1
```

Edges connect point ids:

```csv
source,target
A,B
```

## Capabilities

- load point and edge CSV files
- edit point and edge tables in the GUI
- validate duplicate point IDs
- validate missing edge references
- project 3D coordinates into a 2D canvas using `numpy`
- parse editable table data using `pandas`
- render connected wireframe shapes
- adjust rotation and scale controls

## Current Limits

Vsee is currently a coordinate viewer. Saved scenes, richer primitives, camera presets, animation, live data binding, and real projection/hologram output are future work.
