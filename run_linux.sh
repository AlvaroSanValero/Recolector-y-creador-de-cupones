#!/bin/bash
# Ejecuta el script en sistemas Linux
DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$DIR/coupon_harvester.py"
