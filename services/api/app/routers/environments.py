"""Shim: re-exports from hexagonal adapter location.

Kept for backward compatibility. New code should import from
app.adapters.primary.http.environments directly.
"""

from app.adapters.primary.http.environments import router  # noqa: F401
