from __future__ import annotations
import os, sys
from pathlib import Path


def bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath("resources", *parts)


def app_data_dir() -> Path:
    override = os.environ.get("THERA_CURATOR_DATA_DIR")
    if override:
        p = Path(override)
    elif os.name == "nt":
        p = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or Path.home()) / "TheraSAbDabWHOInnCurator"
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "TheraSAbDabWHOInnCurator"
    else:
        p = Path(os.environ.get("XDG_DATA_HOME", Path.home()/".local"/"share")) / "TheraSAbDabWHOInnCurator"
    p.mkdir(parents=True, exist_ok=True)
    return p


def database_path() -> Path:
    return app_data_dir() / "curator.sqlite"


def backups_dir() -> Path:
    p = app_data_dir() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def imports_dir() -> Path:
    p = app_data_dir() / "imports"
    p.mkdir(parents=True, exist_ok=True)
    return p
