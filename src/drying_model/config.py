"""Project configuration and shared path helpers.

The configuration is written in YAML (JSON is accepted as well, since it is a
subset of YAML).  PyYAML is preferred; if it is unavailable a JSON parser is
used, so a JSON-formatted file with a .yaml/.json extension still loads.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except Exception:
        return json.loads(text)


def load_config(path=None) -> dict:
    if path is None:
        path = PROJECT_ROOT / "configs" / "main.yaml"
    path = Path(path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    cfg = _read_config(path)
    cfg["_config_path"] = str(path)
    return cfg


def load_sweeps(path=None) -> dict:
    if path is None:
        path = PROJECT_ROOT / "configs" / "sensitivity.yaml"
    path = Path(path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return _read_config(path)


def cfg_path(cfg: dict, key: str, section: str = "paths") -> Path:
    p = Path(cfg[section][key])
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
