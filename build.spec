# -*- mode: python ; coding: utf-8 -*-

# MapHelper - PyInstaller Build Spec
# This creates a standalone single-file executable with all resources embedded

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('maps', 'maps'),           # Embed map templates
        ('fonts', 'fonts'),         # Embed custom fonts
    ],
    hiddenimports=[
        'cv2',
        'numpy',
        'mss',
        'keyboard',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'utils.resource_path',      # Ensure resource path util is included
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single-file executable (--onefile)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MapHelper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                      # Compress with UPX
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                 # No console window (GUI app)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                     # Add icon='icon.ico' if you have one
)
