"""Shim: re-exports from app.infrastructure.database.

Kept for backward compatibility. New code should import from
app.infrastructure.database directly.
"""

from app.infrastructure.database import (  # noqa: F401
    async_session_factory,
    engine,
    get_db,
    init_db,
)
from app.infrastructure.orm_models import Base  # noqa: F401
