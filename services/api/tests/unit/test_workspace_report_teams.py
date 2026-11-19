"""Filtro de vários times no relatório."""

from __future__ import annotations

import uuid

from app.application.use_cases._workspace_report_teams import (
    MAX_TEAM_FILTERS,
    NO_TEAM_FILTER,
    normalize_teams,
    team_matches,
)
from app.ports.workspace_report import ReportConversation


def _conv(team: str | None) -> ReportConversation:
    return ReportConversation(uuid.uuid4(), uuid.uuid4(), "a@x.com", "t", team=team)


def test_normalize_teams_trims_dedupes_and_limits() -> None:
    assert normalize_teams(None) == ()
    assert normalize_teams(["  PRIME   SP ", "prime sp", "", "ÁGIL"]) == ("PRIME SP", "ÁGIL")
    assert len(normalize_teams([f"t{i}" for i in range(80)])) == MAX_TEAM_FILTERS


def test_team_matches_any_of_the_chosen_teams() -> None:
    assert team_matches(_conv("SPED"), ())
    assert team_matches(_conv("SPED"), ("ágil", "sped"))
    assert not team_matches(_conv("SPED"), ("ÁGIL",))
    assert team_matches(_conv(None), ("ÁGIL", NO_TEAM_FILTER))
    assert not team_matches(_conv(None), ("ÁGIL",))
