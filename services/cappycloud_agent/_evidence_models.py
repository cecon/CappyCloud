"""Tipos internos da coleta automática de evidências."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _ConfluenceSource:
    base_url: str
    space: str
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class _CodeHit:
    query: str
    repo: str
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class _DocHit:
    query: str
    title: str
    url: str
    summary: str


@dataclass(frozen=True)
class _DocSearchAttempt:
    query: str
    source: _ConfluenceSource


@dataclass(frozen=True)
class _ParameterDirectory:
    repo: str
    path: str
    preferred: bool = False
