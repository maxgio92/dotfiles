#!/bin/sh
# Print a greeting for the name given as the first argument.
set -eu
printf 'Hello, %s\n' "${1:-world}"
