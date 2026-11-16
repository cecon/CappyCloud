"""Times no relatório: filtro e quadro "Por time".

O time vem do acesso da pessoa ao workspace; quem não tem time entra em
``NO_TEAM_LABEL``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.ports.workspace_report import ReportConversation

COST_DIGITS = 6
NO_TEAM_FILTER = "__none__"
NO_TEAM_LABEL = "Sem time"


@dataclass(frozen=True)
class TeamRow:
    name: str
    analysts: int
    questions: int
    conversations: int
    cost_usd: float
    share: float  # fração das perguntas do período (0 a 1)


def money(value: float) -> float:
    return round(value, COST_DIGITS)


def team_matches(conv: ReportConversation, team: str | None) -> bool:
    if team is None:
        return True
    if team == NO_TEAM_FILTER:
        return conv.team is None
    return (conv.team or "").lower() == team.lower()


def analyst_team(pairs: Iterable[tuple[str, str]], email: str) -> str:
    """Time da pessoa a partir de ``(email, time)``; com times diferentes, junta os nomes."""
    names = sorted({name for who, name in pairs if who == email}, key=str.lower)
    return " / ".join(names)


def team_rows(
    pairs: Iterable[tuple[str, str]],
    grouped: Mapping[str, tuple[int, int, float]],
    total_questions: int,
) -> list[TeamRow]:
    """``pairs``: (email, time) por conversa; ``grouped``: time → (conversas, perguntas, custo)."""
    analysts: dict[str, set[str]] = defaultdict(set)
    for email, name in pairs:
        analysts[name].add(email)
    teams = [
        TeamRow(
            name=name,
            analysts=len(analysts[name]),
            questions=questions,
            conversations=convs,
            cost_usd=money(cost),
            share=round(questions / total_questions, 4) if total_questions else 0.0,
        )
        for name, (convs, questions, cost) in grouped.items()
    ]
    teams.sort(key=lambda t: (t.name == NO_TEAM_LABEL, -t.questions, -t.cost_usd, t.name.lower()))
    return teams
