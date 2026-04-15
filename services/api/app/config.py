"""Shim: re-exports from app.infrastructure.config.

Kept for backward compatibility. New code should import from
app.infrastructure.config directly.
"""

from app.infrastructure.config import (  # noqa: F401
    Settings,
    cors_origins_list,
    get_settings,
)
