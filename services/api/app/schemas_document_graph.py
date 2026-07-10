"""Pydantic schemas for document graph search."""

from __future__ import annotations

from pydantic import BaseModel


class DocumentGraphSearchResult(BaseModel):
    title: str
    source_url: str | None = None
    summary: str
    score: float
