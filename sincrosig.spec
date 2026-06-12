# sincrosig.spec  — PyInstaller spec file
# Uso: pyinstaller sincrosig.spec

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# ── Datos adicionales a empaquetar ─────────────────────────────────────────────
datas = []
# ttkbootstrap themes / assets
datas += collect_data_files("ttkbootstrap")
# Pillow plugins (iconos, imágenes)
datas += collect_data_files("PIL")

# ── Imports ocultos (importados dinámicamente) ─────────────────────────────────
hiddenimports = (
    collect_submodules("mysql.connector")
    + collect_submodules("ttkbootstrap")
    + collect_submodules("PIL")
    + [
        "requests",
        "packaging",
        "babel",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "openpyxl",
        "xlsxwriter",
        "pandas",
        "numpy",
    ]
)

a = Analysis(
    ["app.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "IPython", "jupyter"],
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
    name="SincroSIG",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                          # sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="file_version_info.txt",        # metadatos Windows
    # icon="assets/icon.ico",              # descomentar si tenés un .ico
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SincroSIG",
)
