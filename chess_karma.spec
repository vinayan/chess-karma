# chess_karma.spec  –  PyInstaller build specification for Chess Karma
# Run:  pyinstaller chess_karma.spec

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Sound assets  (WAV files used at runtime)
        ('chess_karma/assets/sounds/*.wav', 'chess_karma/assets/sounds'),
        # App icons
        ('chess_karma/assets/icon.ico', 'chess_karma/assets'),
        ('chess_karma/assets/icon.png', 'chess_karma/assets'),
        # Blank schema DB copied to ~/chess_karma.db on first launch
        ('chess_karma_blank.db', '.'),
    ],
    hiddenimports=[
        'chess.svg',
        'chess.pgn',
        'miniaudio',
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
    name='Chess Karma',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX triggers AV false positives — keep disabled
    console=False,           # no console window
    icon='chess_karma/assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,               # UPX triggers AV false positives — keep disabled
    upx_exclude=[],
    name='Chess Karma',
)
