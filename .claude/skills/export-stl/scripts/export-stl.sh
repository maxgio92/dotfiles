#!/bin/bash

# OpenSCAD to STL Exporter with Geometry Validation
# Converts .scad files to .stl for 3D printing
# Checks for non-manifold geometry and other printability issues

set -e

# Default values
OUTPUT=""
FORMAT="binstl"  # Binary STL by default

# OpenSCAD path (macOS default)
OPENSCAD="/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"

# Check if OpenSCAD exists
if [[ ! -x "$OPENSCAD" ]]; then
    if command -v openscad &> /dev/null; then
        OPENSCAD="openscad"
    else
        echo "Error: OpenSCAD not found at $OPENSCAD or in PATH"
        echo "Please install OpenSCAD from https://openscad.org/"
        exit 1
    fi
fi

# Parse arguments
INPUT=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --binary)
            FORMAT="binstl"
            shift
            ;;
        --ascii)
            FORMAT="asciistl"
            shift
            ;;
        --help|-h)
            echo "Usage: export-stl.sh <input.scad> [options]"
            echo ""
            echo "Options:"
            echo "  --output <path>   Output STL path (default: <input>.stl)"
            echo "  --binary          Binary STL format (default, smaller)"
            echo "  --ascii           ASCII STL format (human-readable)"
            echo ""
            echo "Performs geometry validation during export:"
            echo "  - Non-manifold edges (holes in mesh)"
            echo "  - Self-intersecting geometry"
            echo "  - Degenerate faces"
            echo ""
            echo "Example:"
            echo "  export-stl.sh model.scad"
            echo "  export-stl.sh model.scad --output print_ready.stl"
            exit 0
            ;;
        -*)
            echo "Unknown option: $1"
            exit 1
            ;;
        *)
            if [[ -z "$INPUT" ]]; then
                INPUT="$1"
            else
                echo "Error: Multiple input files specified"
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate input
if [[ -z "$INPUT" ]]; then
    echo "Error: No input file specified"
    echo "Usage: export-stl.sh <input.scad> [options]"
    exit 1
fi

if [[ ! -f "$INPUT" ]]; then
    echo "Error: Input file not found: $INPUT"
    exit 1
fi

# Determine output path
if [[ -z "$OUTPUT" ]]; then
    BASENAME="${INPUT%.scad}"
    OUTPUT="${BASENAME}.stl"
fi

echo "========================================"
echo "Export STL: $(basename "$INPUT")"
echo "========================================"
echo ""

# Build OpenSCAD command
CMD=("$OPENSCAD")
CMD+=("--export-format" "$FORMAT")
CMD+=("-o" "$OUTPUT")
CMD+=("$INPUT")

# Run OpenSCAD and capture all output (warnings go to stderr)
echo "Rendering and exporting..."
RESULT=$("${CMD[@]}" 2>&1) || true
EXIT_CODE=$?

# Check for geometry warnings
WARNINGS=""
HAS_ISSUES=false

if echo "$RESULT" | grep -qi "not.*manifold\|non-manifold"; then
    WARNINGS="$WARNINGS\n- Non-manifold geometry detected (mesh has holes)"
    HAS_ISSUES=true
fi

if echo "$RESULT" | grep -qi "self-intersect"; then
    WARNINGS="$WARNINGS\n- Self-intersecting geometry detected"
    HAS_ISSUES=true
fi

if echo "$RESULT" | grep -qi "degenerate"; then
    WARNINGS="$WARNINGS\n- Degenerate faces detected (zero-area triangles)"
    HAS_ISSUES=true
fi

if echo "$RESULT" | grep -qi "WARNING\|warning"; then
    # Capture other warnings
    OTHER_WARNS=$(echo "$RESULT" | grep -i "warning" | head -5)
    if [[ -n "$OTHER_WARNS" ]]; then
        WARNINGS="$WARNINGS\n- Other warnings:\n$OTHER_WARNS"
    fi
fi

# Check if export succeeded
if [[ -f "$OUTPUT" ]]; then
    SIZE=$(ls -lh "$OUTPUT" | awk '{print $5}')

    # Get triangle count from binary STL
    if [[ "$FORMAT" == "binstl" ]]; then
        TRIANGLES=$(od -An -tu4 -j80 -N4 "$OUTPUT" | tr -d ' ')
    fi

    echo ""
    echo "--- Export Results ---"
    echo "Output: $OUTPUT"
    echo "Size: $SIZE"
    if [[ -n "$TRIANGULAR" ]]; then
        echo "Triangles: $TRIANGLES"
    fi

    # Report geometry validation
    echo ""
    echo "--- Geometry Validation ---"

    if [[ "$HAS_ISSUES" == true ]]; then
        echo "STATUS: WARNING - Issues detected"
        echo -e "$WARNINGS"
        echo ""
        echo "The model may still print, but consider fixing these issues:"
        echo "- Non-manifold: Ensure all shapes are closed solids"
        echo "- Self-intersect: Use union() to properly combine overlapping shapes"
        echo "- Degenerate: Check for very thin or zero-thickness features"
    else
        echo "STATUS: PASSED - No geometry issues detected"
        echo "- Mesh appears manifold (watertight)"
        echo "- No self-intersections found"
        echo "- Ready for slicing"
    fi

    echo ""
    echo "========================================"
    if [[ "$HAS_ISSUES" == true ]]; then
        echo "RESULT: Exported with warnings"
    else
        echo "RESULT: Export successful"
    fi
    echo "========================================"

else
    echo ""
    echo "--- Export Failed ---"
    echo "OpenSCAD output:"
    echo "$RESULT"
    echo ""
    echo "========================================"
    echo "RESULT: Export failed"
    echo "========================================"
    exit 1
fi
