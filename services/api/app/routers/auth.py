"""Shim: re-exports router from new hexagonal location.

This file exists for backwards compatibility during migration.
Once confirmed stable, update app/main.py to import from
app.adapters.primary.http.auth directly and delete this file.
"""

from app.adapters.primary.http.auth import router  # noqa: F401
