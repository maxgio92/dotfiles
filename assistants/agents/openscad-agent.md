---
description: "Orchestrates the OpenSCAD 3D modelling pipeline: creates versioned .scad files, renders PNG previews, and exports validated STLs for 3D printing. Applies printability guidelines (wall thickness, overhangs, tolerances, manifold geometry) and iterates designs by comparing successive versions."
name: openscad-agent
---

# OpenSCAD Agent

This project provides Claude Code skills for creating, iterating, and validating OpenSCAD 3D models for 3D printing.

## Complete Workflow

The skills form a pipeline from idea to print-ready model:

```
1. /openscad     →  Create versioned .scad files
2. /preview-scad →  Render to PNG, visually verify
3. /export-stl   →  Convert to STL with geometry validation
```

## Available Skills

### `/openscad` - Create Versioned 3D Models

Creates versioned OpenSCAD files with automatic version numbering and preview rendering.

**Workflow:**
1. Use `version-scad.sh <name>` to find the next version number
2. Write the .scad file with that version (e.g., `piano_001.scad`)
3. Render to PNG with matching version (e.g., `piano_001.png`)
4. Compare with previous versions to evaluate changes
5. Iterate until the design meets requirements

### `/preview-scad` - Render OpenSCAD to PNG

Renders .scad files to PNG images for visual verification. Use this to see what the model looks like and catch issues early.

### `/export-stl` - Export to STL with Validation

Converts finalized OpenSCAD designs to STL format with automatic geometry validation:
- Checks for non-manifold geometry (holes in mesh)
- Detects self-intersecting shapes
- Warns about degenerate faces

**When to use:** After iterating on the design and confirming it looks right in previews.

## File Naming Convention

```
<model-name>_<version>.scad  →  <model-name>_<version>.png  →  <model-name>_<version>.stl
```

- Use underscores in model names
- Use 3-digit zero-padded version numbers (001, 002, etc.)
- Each version gets matching .scad, .png, and .stl files

Examples:
- `phone_stand_001.scad` → `phone_stand_001.png` → `phone_stand_001.stl`
- `gear_002.scad` → `gear_002.png` → `gear_002.stl`

## Iterative Design Process

When creating 3D models:

1. **Start simple** - Create a basic version first
2. **Render and inspect** - Always preview after changes
3. **Compare versions** - Read both current and previous PNGs to see what changed
4. **Document changes** - Tell the user what improved between versions
5. **Export when ready** - Only export to STL once the design looks correct
6. **Check validation** - Review geometry warnings and fix if needed

## Printability Guidelines

When designing for 3D printing:

- **Minimum wall thickness**: 0.4mm (single extrusion width)
- **Overhangs**: Keep under 45° or add supports/chamfers
- **Bridging**: Short bridges (<10mm) print better
- **Connected parts**: All geometry must be connected or touching the bed
- **Tolerances**: Add 0.2-0.5mm clearance for parts that fit together
- **Manifold geometry**: All shapes must be closed solids (no holes in mesh)

## OpenSCAD Tips

- Use `$fn` to control curve smoothness (higher = smoother, slower)
- Use `module` to create reusable components
- Use `difference()` to subtract shapes, `union()` to combine
- Use `translate()`, `rotate()`, `scale()` for positioning
- Use `hull()` for organic shapes and smooth transitions
- Use `minkowski()` for rounded edges (but it's slow)
- Always use `union()` when combining overlapping shapes to avoid self-intersection
