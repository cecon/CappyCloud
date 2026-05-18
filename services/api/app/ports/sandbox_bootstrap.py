"""Port para materializar a configuração de periféricos dentro de um container
de sandbox (ADR-004 §5).

O bootstrap é idempotente: chamar várias vezes deve produzir o mesmo estado
final. Cobre 3 destinos dentro de ``~/.claude/``:

- ``settings.json`` (MCPs)
- ``skills/<name>/SKILL.md`` (skills globais por sandbox)
- ``agents/<name>.md`` (subagents globais por sandbox, com frontmatter YAML)

Cada método é responsável por LIMPAR o destino antes de escrever (single
source of truth = DB; edições manuais dentro do container são perdidas).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities import Sandbox, SandboxAgent, SandboxSkill


class SandboxBootstrapGateway(ABC):
    """Materializa o cadastro (DB) em arquivos dentro do container."""

    @abstractmethod
    async def write_settings_json(self, sandbox: Sandbox, settings: dict) -> None:
        """Escreve ``settings`` em ``~/.claude/settings.json`` no container.

        ``settings`` é o dict pronto (ex.: ``{"mcpServers": {...}}``).
        Levanta :class:`BootstrapFailureError` se a escrita falhar.
        """

    @abstractmethod
    async def write_skills(self, sandbox: Sandbox, skills: list[SandboxSkill]) -> None:
        """Materializa todas as skills habilitadas em ``~/.claude/skills/``.

        Apaga a pasta antes (single source of truth = DB). Cada skill vira
        ``~/.claude/skills/<name>/SKILL.md`` com markdown do ``content``.
        """

    @abstractmethod
    async def write_agents(self, sandbox: Sandbox, agents: list[SandboxAgent]) -> None:
        """Materializa todos os agents habilitados em ``~/.claude/agents/``.

        Apaga a pasta antes. Cada agent vira ``~/.claude/agents/<name>.md``
        com frontmatter YAML (name/description/tools/model) e corpo
        = ``system_prompt``.
        """


class BootstrapFailureError(Exception):
    """Falha ao materializar arquivos no container."""
