# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Autotask Time Entry
# Build with: pyinstaller AutotaskTimeEntry.spec

from PyInstaller.building.build_main import Analysis, PYZ, EXE, BUNDLE, COLLECT
import os

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src', 'src'),
    ],
    hiddenimports=[
        'anthropic',
        'requests',
        'dotenv',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.simpledialog',
        'tkinter.filedialog',
        'difflib',
        'calendar',
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TimeSlip',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # No terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TimeSlip',
)

app = BUNDLE(
    coll,
    name='TimeSlip.app',
    icon='timeslip.icns',
    bundle_identifier='com.jdkconsulting.timeslip',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'CFBundleDisplayName': 'TimeSlip',
        'CFBundleShortVersionString': '1.30',
        'CFBundleName': 'TimeSlip',
        'LSMinimumSystemVersion': '13.0',
        'NSHighResolutionCapable': True,
    },
)
