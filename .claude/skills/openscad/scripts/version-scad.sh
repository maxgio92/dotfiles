#!/bin/bash

# OpenSCAD Version Helper
# Finds the next available version number for a model name

set -e

if [[ -z "$1" ]]; then
    echo "Usage: version-scad.sh <model-name>"
    echo ""
    echo "Finds existing versions and returns the next version number."
    echo ""
    echo "Example:"
    echo "  version-scad.sh piano"
    echo "  # If piano_001.scad and piano_002.scad exist, outputs: piano_003"
    exit 1
fi

MODEL_NAME="$1"

# Find existing versioned files for this model
EXISTING=$(ls -1 "${MODEL_NAME}_"[0-9][0-9][0-9].scad 2>/dev/null | sort -V | tail -1 || true)

if [[ -z "$EXISTING" ]]; then
    # No existing versions, start at 001
    NEXT_VERSION="001"
    echo "No existing versions found for '${MODEL_NAME}'"
    echo "Next version: ${MODEL_NAME}_001"
    echo ""
    echo "Create: ${MODEL_NAME}_001.scad"
else
    # Extract version number and increment
    CURRENT_VERSION=$(echo "$EXISTING" | sed -E "s/${MODEL_NAME}_([0-9]{3})\.scad/\1/")
    NEXT_NUM=$((10#$CURRENT_VERSION + 1))
    NEXT_VERSION=$(printf "%03d" $NEXT_NUM)

    echo "Existing versions:"
    ls -1 "${MODEL_NAME}_"[0-9][0-9][0-9].scad 2>/dev/null | sort -V
    echo ""
    echo "Latest: ${EXISTING}"
    echo "Next version: ${MODEL_NAME}_${NEXT_VERSION}"
    echo ""
    echo "Create: ${MODEL_NAME}_${NEXT_VERSION}.scad"
fi
