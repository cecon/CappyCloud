"""Shim: re-exports from new hexagonal locations.

Kept for backward compatibility. New code should import from
app.adapters.primary.http.deps directly.
"""

from app.adapters.primary.http.deps import (  # noqa: F401
    get_authenticated_user as get_current_user,
)
