#!/bin/bash

# OpenSCAD Preview Renderer
# Renders .scad files to PNG images for visual verification

set -e

# Default values
SIZE="800x600"
COLORSCHEME="Cornfield"
RENDER_MODE="preview"
OUTPUT=""
CAMERA=""

# OpenSCAD path (macOS default)
OPENSCAD="/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"

# Check if OpenSCAD exists
if [[ ! -x "$OPENSCAD" ]]; then
    # Try finding it in PATH
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
        --size)
            SIZE="$2"
            shift 2
            ;;
        --camera)
            CAMERA="$2"
            shift 2
            ;;
        --colorscheme)
            COLORSCHEME="$2"
            shift 2
            ;;
        --render)
            RENDER_MODE="render"
            shift
            ;;
        --preview)
            RENDER_MODE="preview"
            shift
            ;;
        --help|-h)
            echo "Usage: render-scad.sh <input.scad> [options]"
            echo ""
            echo "Options:"
            echo "  --output <path>       Output PNG path (default: <input>_preview.png)"
            echo "  --size <WxH>          Image size (default: 800x600)"
            echo "  --camera <params>     Camera position: x,y,z,tx,ty,tz,d"
            echo "  --colorscheme <name>  Color scheme (default: Cornfield)"
            echo "  --render              Full render mode (slower, accurate)"
            echo "  --preview             Preview mode (faster, default)"
            echo ""
            echo "Example:"
            echo "  render-scad.sh model.scad --size 1024x768"
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
    echo "Usage: render-scad.sh <input.scad> [options]"
    exit 1
fi

if [[ ! -f "$INPUT" ]]; then
    echo "Error: Input file not found: $INPUT"
    exit 1
fi

# Determine output path
if [[ -z "$OUTPUT" ]]; then
    # Remove .scad extension and add _preview.png
    BASENAME="${INPUT%.scad}"
    OUTPUT="${BASENAME}_preview.png"
fi

# Build OpenSCAD command
CMD=("$OPENSCAD")
CMD+=("--viewall" "--autocenter")
CMD+=("--imgsize" "${SIZE/x/,}")
CMD+=("--colorscheme" "$COLORSCHEME")

if [[ -n "$CAMERA" ]]; then
    CMD+=("--camera" "$CAMERA")
fi

if [[ "$RENDER_MODE" == "preview" ]]; then
    CMD+=("--preview")
fi

CMD+=("-o" "$OUTPUT")
CMD+=("$INPUT")

# Run OpenSCAD
echo "Rendering: $INPUT -> $OUTPUT"
echo "Mode: $RENDER_MODE, Size: $SIZE"

if OUTPUT=$("${CMD[@]}" 2>&1); then
    if [[ -f "$OUTPUT" ]]; then
        echo "Success: Preview saved to $OUTPUT"
    else
        # OpenSCAD succeeded but check if file exists
        if [[ -f "${BASENAME}_preview.png" ]]; then
            echo "Success: Preview saved to ${BASENAME}_preview.png"
        fi
    fi
else
    echo "OpenSCAD output:"
    echo "$OUTPUT"
    exit 1
fi
