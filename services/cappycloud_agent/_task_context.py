"""Fase "contexto" do turno: monta o prompt que vai para o runtime do agente."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from ._evidence_prefetch import inject_evidence_prefetch
from ._pipeline_helpers import build_prompt_with_worktree_context
from ._worktree_validation import validate_and_inject_worktree

EmitPhase = Callable[..., Awaitable[None]]


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


async def prepare_turn_prompt(
    *,
    emit_phase: EmitPhase,
    pool,
    task_id: str,
    prompt: str,
    user_message: str | None,
    resumed_cli_session: bool,
    sandbox_session_url: str,
    repos: list,
    session_root: str,
    working_directory: str,
) -> str | None:
    """Prompt do turno, ou ``None`` se o worktree não pôde ser validado.

    Sessão do Claude CLI retomada: vai só a mensagem do usuário — o contexto da
    primeira mensagem (workspace, estrutura dos repositórios, evidências) já
    está no histórico do Claude Code. Os worktrees continuam sendo conferidos.
    """
    started = time.monotonic()
    pipeline_prompt = prompt
    lean = resumed_cli_session and bool(user_message)
    label = "Retomando a sessão" if lean else "Preparando contexto"
    await emit_phase(task_id, "context", label, "active")

    if lean:
        prompt = user_message or prompt
    else:
        prompt = await build_prompt_with_worktree_context(
            prompt, sandbox_session_url, repos, session_root
        )

    if sandbox_session_url and repos:
        validated = await validate_and_inject_worktree(
            pool=pool,
            task_id=task_id,
            prompt=prompt,
            repos=repos,
            sandbox_session_url=sandbox_session_url,
            session_root=session_root,
            working_directory=working_directory,
        )
        if validated is None:
            return None
        if not lean:
            prompt = validated

    if not lean:
        prompt = await inject_evidence_prefetch(
            prompt,
            user_message=pipeline_prompt,
            sandbox_session_url=sandbox_session_url,
            repos=repos,
            session_root=session_root,
        )
    done_label = "Sessão retomada" if lean else "Contexto preparado"
    await emit_phase(task_id, "context", done_label, "done", duration_ms=_elapsed_ms(started))
    return prompt
