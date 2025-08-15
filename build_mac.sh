#!/bin/bash
# Build macOS executable with PyInstaller (run on macOS)
python3 -m pip install pyinstaller
pyinstaller --onefile --windowed --name coupon_harvester_v2 coupon_harvester_v2.py
echo "Build complete. Check dist/coupon_harvester_v2"
