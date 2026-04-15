"""Shim: re-exports from app.infrastructure.orm_models.

Kept for backward compatibility. New code should import from
app.infrastructure.orm_models directly.
"""

from app.infrastructure.orm_models import (  # noqa: F401
    Base,
    Conversation,
    Message,
    User,
)
