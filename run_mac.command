#!/bin/bash
# Ejecuta el script en macOS (make executable if needed)
DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$DIR/coupon_harvester.py"
