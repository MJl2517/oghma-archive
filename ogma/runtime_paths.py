from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping


PRODUCT_DIRECTORY_NAME = "Oghma Archive"


def bundle_root(source_root: Path) -> Path:
    """Return the read-only application resource root."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and frozen_root:
        return Path(frozen_root).resolve()
    return source_root.resolve()


def default_data_dir(
    source_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
    frozen: bool | None = None,
) -> Path:
    """Return a writable data location for source and packaged launches."""
    environment = os.environ if environ is None else environ
    configured = environment.get("OGMA_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if not is_frozen:
        return (source_root / "data").resolve()

    local_app_data = environment.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / "AppData" / "Local"
    return (base / PRODUCT_DIRECTORY_NAME / "data").resolve()
