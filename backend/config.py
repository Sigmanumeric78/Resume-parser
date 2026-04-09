"""
Backend configuration module.

Reads environment variables and exposes a `config` object.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


def _get_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_list(value: str, default: List[str]) -> List[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Config:
    HOST: str
    DEBUG: bool
    ALLOWED_ORIGINS: List[str]


def _load_config() -> Config:
    host = os.environ.get("HOST", "0.0.0.0")
    debug = _get_bool(os.environ.get("DEBUG", "0"), default=False)
    allowed_origins = _get_list(
        os.environ.get("ALLOWED_ORIGINS", ""),
        default=["*"],
    )
    return Config(HOST=host, DEBUG=debug, ALLOWED_ORIGINS=allowed_origins)


config = _load_config()
