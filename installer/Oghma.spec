# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path, PurePosixPath


project_root = Path(SPECPATH).resolve().parent

excluded_static_patterns = (
    "img/ogma-icon.svg",
    "img/backgrounds/archive-bg-*.jpg",
    "img/backgrounds/contact-sheet.jpg",
    "img/backgrounds/ogma-bg-1.jpg",
    "img/backgrounds/ogma-bg-3.jpg",
    "img/backgrounds/ogma-bg-9.jpg",
    "img/backgrounds/page-bg-ogma-green.jpg",
    "img/themes/**/*.jpg",
)


def include_static_file(path: Path) -> bool:
    relative = PurePosixPath(path.relative_to(project_root / "static").as_posix())
    return not any(relative.match(pattern) for pattern in excluded_static_patterns)


static_datas = [
    (str(path), str(Path("static") / path.relative_to(project_root / "static").parent))
    for path in (project_root / "static").rglob("*")
    if path.is_file() and include_static_file(path)
]

a = Analysis(
    [str(project_root / "scripts" / "ogma_tray.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "templates"), "templates"),
        (str(project_root / "materials"), "materials"),
        (str(project_root / "installer" / "launch-update.ps1"), "installer"),
        *static_datas,
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Oghma",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "static" / "img" / "ogma-icon.ico"),
    version=str(project_root / "build" / "version-info.txt"),
    contents_directory="_internal",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Oghma",
)
