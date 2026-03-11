# chess_karma_mac.spec  –  PyInstaller build spec for Chess Karma (macOS)
# Run:  pyinstaller chess_karma_mac.spec --clean --noconfirm
#
# Produces:  dist/Chess Karma.app
# Prerequisite: tools/create_icns.py must have been run first
#               to generate chess_karma/assets/icon.icns

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Sound assets  (WAV files used at runtime)
        ('chess_karma/assets/sounds/*.wav', 'chess_karma/assets/sounds'),
        # App icons
        ('chess_karma/assets/icon.icns', 'chess_karma/assets'),
        ('chess_karma/assets/icon.png',  'chess_karma/assets'),
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
    upx=False,
    console=False,
    icon='chess_karma/assets/icon.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Chess Karma',
)

# macOS-only: wrap the collected output into a .app bundle
app = BUNDLE(
    coll,
    name='Chess Karma.app',
    icon='chess_karma/assets/icon.icns',
    bundle_identifier='com.chesskarma.app',
    info_plist={
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleVersion':            '0.1.0',
        'NSHighResolutionCapable':    True,
        'NSRequiresAquaSystemAppearance': False,   # respect Dark Mode
        'CFBundleDocumentTypes': [],
    },
)
