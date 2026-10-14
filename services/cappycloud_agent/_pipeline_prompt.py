"""Montagem do prompt do Pipeline: contexto do repo, subagentes e SigNoz."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ._agent_context import (
    build_prompt_with_agent,
    load_agent_context,
    load_repo_agent_profiles,
)
from ._agent_runtime_lookup import resolve_agent_runtime
from ._agent_session import AGENT_RUNTIME_CLAUDE_CLI
from ._claude_cli_resume import claude_cli_agent_names
from ._pipeline_helpers import db_url
from ._signoz_context import (
    build_signoz_context_section,
    fetch_signoz_service_names,
    has_enabled_signoz_mcp,
)

log = logging.getLogger("services.cappycloud_agent.cappycloud_pipeline")


class PipelinePromptMixin:
    """Métodos do Pipeline que montam o prompt enviado ao agente."""

    valves: Any
    _env_manager: Any
    _run: Callable[..., Any]

    def _native_subagents(self, sandbox_id: str, session_url: str) -> set[str]:
        """Subagentes que o Claude CLI carrega de ~/.claude/agents neste sandbox."""
        try:
            runtime = self._run(resolve_agent_runtime(db_url(), sandbox_id), timeout=5)
            if runtime != AGENT_RUNTIME_CLAUDE_CLI:
                return set()
            return self._run(claude_cli_agent_names(session_url), timeout=10)
        except Exception as exc:
            log.warning("Falha ao listar os subagentes da sandbox %s: %s", sandbox_id, exc)
            return set()

    def _build_pipe_prompt(
        self,
        user_message: str,
        repos: list,
        session_root: str,
        sandbox_id: str,
        execution_profile: str,
    ) -> tuple[str, str]:
        """Devolve ``(prompt, sandbox_session_url)`` para o dispatch."""
        repo_ids: list[str] = [r["repo_id"] for r in repos if r.get("repo_id")]

        skills_top: list[dict] = []
        agent_profiles: list[dict] = []
        if repo_ids:
            try:
                skills_top = self._run(
                    load_agent_context(
                        self.valves.DATABASE_URL,
                        user_message,
                        repo_ids=repo_ids or None,
                    ),
                    timeout=10,
                )
            except Exception as exc:
                log.warning("Falha ao carregar agent_context: %s", exc)
        if repos:
            try:
                agent_profiles = self._run(
                    load_repo_agent_profiles(
                        self.valves.DATABASE_URL,
                        repos,
                        sandbox_id=sandbox_id,
                    ),
                    timeout=5,
                )
            except Exception as exc:
                log.warning("Falha ao carregar repo_agent_profiles: %s", exc)

        sandbox_host = self.valves.SANDBOX_HOST
        sandbox_session_port = self.valves.SANDBOX_SESSION_PORT
        if self._env_manager is not None:
            try:
                sandbox_host, _, sandbox_session_port, _ = self._run(
                    self._env_manager._resolve_sandbox_endpoint(sandbox_id),
                    timeout=5,
                )
            except Exception as exc:
                log.warning("Falha ao resolver endpoint da sandbox %s: %s", sandbox_id, exc)
        sandbox_session_url = f"http://{sandbox_host}:{sandbox_session_port}"

        # NOTA: a estrutura top-level do worktree é injetada pelo dispatcher,
        # depois de o worktree ser efetivamente criado pelo EnvironmentManager.
        # Tentar obtê-la aqui falha sempre na primeira mensagem (worktree ainda
        # não existe → /worktree/ls-files devolve 500).
        prompt = build_prompt_with_agent(
            user_message,
            skills_top,
            sandbox_session_url,
            repos=repos,
            session_root=session_root,
            agent_profiles=agent_profiles,
            execution_profile=execution_profile,
            native_subagents=(
                self._native_subagents(sandbox_id, sandbox_session_url) if agent_profiles else set()
            ),
        )

        # Injeta contexto SigNoz (service.name por repo) se houver configuração.
        repo_ids_for_signoz = [r["repo_id"] for r in repos if r.get("repo_id")]
        if repo_ids_for_signoz:
            try:
                signoz_names = self._run(
                    fetch_signoz_service_names(db_url(), repo_ids_for_signoz),
                    timeout=5,
                )
                signoz_mcp_available = self._run(
                    has_enabled_signoz_mcp(db_url(), sandbox_id),
                    timeout=5,
                )
                signoz_section = build_signoz_context_section(
                    repos,
                    signoz_names,
                    mcp_available=signoz_mcp_available,
                )
                if signoz_section:
                    from ._agent_context import inject_section_before_user_message

                    prompt = inject_section_before_user_message(prompt, signoz_section)
            except Exception as exc:
                log.warning("[Signoz] falha ao injetar contexto: %s", exc)
        return prompt, sandbox_session_url
