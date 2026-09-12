#!/usr/bin/env bash
set -euo pipefail
SVG="$(dirname "$0")/jotmorrow.svg"
for size in 14 16 22 32 48 64 128 192 256; do
  rsvg-convert --width "$size" --height "$size" "$SVG" --output "$(dirname "$0")/jotmorrow-$size.png"
done
