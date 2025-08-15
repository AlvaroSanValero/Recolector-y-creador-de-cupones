# PyInstaller spec file for coupon_harvester_v2
# Use: pyinstaller coupon_harvester_v2.spec
block_cipher = None
a = Analysis(['coupon_harvester_v2.py'],
             pathex=[],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='coupon_harvester_v2', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False )
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name='coupon_harvester_v2')
