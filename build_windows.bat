@echo off
REM Build Windows executable with PyInstaller (run on Windows machine)
python -m pip install pyinstaller
pyinstaller --onefile --windowed --name coupon_harvester_v2 coupon_harvester_v2.py
echo Build complete. Check the dist\coupon_harvester_v2.exe
pause
