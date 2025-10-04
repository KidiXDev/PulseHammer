"""PulseHammer package metadata and feature flags."""
from typing import Optional

TOOL_NAME = "PulseHammer"
VERSION = "0.2.0"

uvloop = None
try:
    import uvloop as _uvloop  # type: ignore
    uvloop = _uvloop
    UVLOOP_AVAILABLE = True
except Exception:
    UVLOOP_AVAILABLE = False

__all__ = ["TOOL_NAME", "VERSION", "uvloop", "UVLOOP_AVAILABLE"]
