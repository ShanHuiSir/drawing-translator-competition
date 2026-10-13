"""Separate read-only application resources from writable user data."""

import os
import sys
from pathlib import Path

# PyInstaller expands resources under _MEIPASS. No downloads happen at runtime.
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
PACKAGE_ROOT = Path(__file__).resolve().parent
# A portable package writes beside itself; an explicit environment override is useful
# for a read-only installation and for isolated integration tests.
APP_ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else RESOURCE_ROOT
DATA_ROOT = Path(os.environ.get("DRAWING_DATA_DIR", APP_ROOT / "workspace"))
MODEL_ROOT = Path(os.environ.get("DRAWING_MODEL_DIR", RESOURCE_ROOT / "models"))


def prepare_storage():
    """
    Create only the app-owned directories; never change the user's originals.
    
    The root is bundle-relative unless DRAWING_DATA_DIR is explicitly supplied.
    Read-only package assets and mutable OCR evidence live in separate trees.
    Jobs retain uploaded copies; the user's selected original is never opened for writing.
    Logs are append-only daily files and cache entries can safely be rebuilt.
    An unwritable destination raises an ordinary filesystem error for the caller.
    This function performs no model installation or network operation.
    """
    for name in ("jobs", "logs", "cache"):
        (DATA_ROOT / name).mkdir(parents=True, exist_ok=True)
