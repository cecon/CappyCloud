"""HTTP adapter for conversation and messaging endpoints — thin glue only."""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import (
    get_authenticated_user,
    get_create_conv_uc,
    get_db_session,
    get_list_convs_uc,
    get_list_msgs_uc,
    get_stream_msg_uc,
)
from app.application.use_cases.conversations import (
    CreateConversation,
    ListConversations,
    ListMessages,
    StreamMessage,
)
from app.domain.entities import User
from app.schemas import ConversationCreate, ConversationOut, MessageOut, SendMessageBody

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ── Existing endpoints ────────────────────────────────────────────────────────


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ListConversations, Depends(get_list_convs_uc)],
) -> list[ConversationOut]:
    """Lista conversas do utilizador."""
    convs = await uc.execute(current.id)
    return [
        ConversationOut(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            environment_id=c.environment_id,
            env_slug=c.env_slug,
        )
        for c in convs
    ]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[CreateConversation, Depends(get_create_conv_uc)],
    body: ConversationCreate | None = None,
) -> ConversationOut:
    """Cria conversa nova, opcionalmente ligada a um ambiente."""
    title = body.title if body and body.title else None
    environment_id = body.environment_id if body else None
    base_branch = body.base_branch if body else None
    conv = await uc.execute(current.id, title, environment_id, base_branch)
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        environment_id=conv.environment_id,
        env_slug=conv.env_slug,
        base_branch=conv.base_branch,
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageOut],
)
async def list_messages(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ListMessages, Depends(get_list_msgs_uc)],
) -> list[MessageOut]:
    """Histórico de mensagens."""
    try:
        msgs = await uc.execute(conversation_id, current.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [
        MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at) for m in msgs
    ]


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: uuid.UUID,
    body: SendMessageBody,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[StreamMessage, Depends(get_stream_msg_uc)],
    cursor: Optional[int] = Query(default=None, description="Último agent_event.id recebido (para reconexão)"),
) -> StreamingResponse:
    """Envia mensagem e devolve resposta do agente em SSE chunks.

    Suporta reconexão via `cursor`: ao passar o último `agent_event.id` recebido,
    o stream retoma a partir desse ponto sem perder eventos.
    """
    try:
        stream = await uc.execute(conversation_id, current.id, body.content, cursor=cursor)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Status endpoint ───────────────────────────────────────────────────────────


@router.get("/{conversation_id}/status")
async def get_conversation_status(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Estado actual do agente para esta conversa.

    Retorna env_status, agent_status, task_id activo e cursor do último evento.
    O frontend usa isto ao abrir/recarregar o chat para saber onde retomar.
    """
    # Verify ownership
    conv_row = await db.execute(
        text("SELECT id FROM conversations WHERE id = :cid AND user_id = :uid"),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    if not conv_row.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")

    # Agent task status
    task_row = await db.execute(
        text(
            """
            SELECT id, status, last_event_at
            FROM agent_tasks
            WHERE conversation_id = :cid
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"cid": str(conversation_id)},
    )
    task = task_row.fetchone()

    agent_status = task.status if task else "idle"
    task_id = str(task.id) if task else None
    last_event_at = task.last_event_at if task else None

    # Last event cursor
    cursor = None
    if task_id:
        ev_row = await db.execute(
            text("SELECT MAX(id) AS max_id FROM agent_events WHERE task_id = :tid"),
            {"tid": task_id},
        )
        ev = ev_row.fetchone()
        cursor = ev.max_id if ev else None

    # Env status via agent port
    env_status = "unknown"
    try:
        agent = request.app.state.agent
        env_slug_row = await db.execute(
            text(
                "SELECT re.slug FROM conversations c "
                "JOIN repo_environments re ON re.id = c.environment_id "
                "WHERE c.id = :cid"
            ),
            {"cid": str(conversation_id)},
        )
        slug_row = env_slug_row.fetchone()
        if slug_row:
            env_info = agent.get_env_status(slug_row.slug)
            env_status = env_info.get("status", "unknown")
    except Exception:
        pass

    return {
        "env_status": env_status,
        "agent_status": agent_status,
        "current_task_id": task_id,
        "last_event_at": last_event_at.isoformat() if last_event_at else None,
        "cursor": cursor,
    }


# ── Diff view ─────────────────────────────────────────────────────────────────


@router.get("/{conversation_id}/diff")
async def get_conversation_diff(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Diff do worktree actual em relação ao branch base.

    Executa `git diff <base_branch>..HEAD` dentro do container Docker
    e devolve as alterações estruturadas por ficheiro.
    """
    import re
    import subprocess

    # Verify ownership + get worktree info
    row = await db.execute(
        text(
            """
            SELECT cs.worktree_path, c.base_branch, re.slug AS env_slug
            FROM conversations c
            LEFT JOIN cappy_sessions cs ON cs.chat_id = c.id::text
            LEFT JOIN repo_environments re ON re.id = c.environment_id
            WHERE c.id = :cid AND c.user_id = :uid
            """
        ),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    conv = row.fetchone()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")

    worktree_path = conv.worktree_path
    base_branch = conv.base_branch or "main"
    env_slug = conv.env_slug

    if not worktree_path or not env_slug:
        return {"base_branch": base_branch, "stats": {"added": 0, "removed": 0}, "files": []}

    # Get container ID from cappy_env_containers
    env_row = await db.execute(
        text("SELECT container_id FROM cappy_env_containers WHERE env_slug = :slug"),
        {"slug": env_slug},
    )
    env = env_row.fetchone()
    if not env:
        return {"base_branch": base_branch, "stats": {"added": 0, "removed": 0}, "files": []}

    try:
        import docker
        client = docker.from_env()
        container = client.containers.get(env.container_id)
        exit_code, output = container.exec_run(
            ["git", "-C", worktree_path, "diff", f"{base_branch}..HEAD"],
        )
        diff_text = output.decode("utf-8", errors="replace") if output else ""
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro ao obter diff: {exc}",
        ) from exc

    return _parse_diff(diff_text, base_branch)


def _parse_diff(diff_text: str, base_branch: str) -> dict:
    """Parse unified diff output into structured format."""
    import re

    files = []
    total_added = 0
    total_removed = 0

    current_file: dict | None = None
    current_hunk: dict | None = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current_file:
                if current_hunk:
                    current_file["hunks"].append(current_hunk)
                files.append(current_file)
            current_file = {"path": "", "hunks": [], "added": 0, "removed": 0}
            current_hunk = None
        elif line.startswith("+++ b/") and current_file is not None:
            current_file["path"] = line[6:]
        elif line.startswith("@@") and current_file is not None:
            if current_hunk:
                current_file["hunks"].append(current_hunk)
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if m:
                current_hunk = {
                    "old_start": int(m.group(1)),
                    "new_start": int(m.group(2)),
                    "lines": [],
                }
        elif current_hunk is not None:
            if line.startswith("+") and not line.startswith("+++"):
                current_hunk["lines"].append({"type": "add", "content": line[1:]})
                if current_file:
                    current_file["added"] += 1
                total_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_hunk["lines"].append({"type": "remove", "content": line[1:]})
                if current_file:
                    current_file["removed"] += 1
                total_removed += 1
            else:
                current_hunk["lines"].append({"type": "context", "content": line[1:] if line.startswith(" ") else line})

    if current_hunk and current_file:
        current_file["hunks"].append(current_hunk)
    if current_file:
        files.append(current_file)

    return {
        "base_branch": base_branch,
        "stats": {"added": total_added, "removed": total_removed},
        "files": files,
    }


# ── Diff comments ─────────────────────────────────────────────────────────────


class DiffCommentIn(BaseModel):
    file_path: str = Field(min_length=1)
    line: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=4096)


@router.post("/{conversation_id}/diff-comments", status_code=status.HTTP_201_CREATED)
async def add_diff_comment(
    conversation_id: uuid.UUID,
    body: DiffCommentIn,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Adiciona comentário inline num ficheiro do diff.

    Os comentários pendentes são injetados automaticamente no próximo prompt
    enviado para esta conversa.
    """
    # Verify ownership
    conv_row = await db.execute(
        text("SELECT id FROM conversations WHERE id = :cid AND user_id = :uid"),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    if not conv_row.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")

    import uuid as _uuid
    comment_id = str(_uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO diff_comments (id, conversation_id, file_path, line, content) "
            "VALUES (:id, :cid, :fp, :ln, :content)"
        ),
        {
            "id": comment_id,
            "cid": str(conversation_id),
            "fp": body.file_path,
            "ln": body.line,
            "content": body.content,
        },
    )
    await db.commit()
    return {"id": comment_id, "conversation_id": str(conversation_id), "bundled": False}


@router.get("/{conversation_id}/diff-comments")
async def list_diff_comments(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    pending_only: bool = Query(default=True),
) -> list[dict]:
    """Lista comentários de diff da conversa."""
    conv_row = await db.execute(
        text("SELECT id FROM conversations WHERE id = :cid AND user_id = :uid"),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    if not conv_row.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")

    q = "SELECT id, file_path, line, content, bundled_at, created_at FROM diff_comments WHERE conversation_id = :cid"
    if pending_only:
        q += " AND bundled_at IS NULL"
    q += " ORDER BY file_path, line"

    rows = await db.execute(text(q), {"cid": str(conversation_id)})
    return [
        {
            "id": str(r.id),
            "file_path": r.file_path,
            "line": r.line,
            "content": r.content,
            "bundled": r.bundled_at is not None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows.fetchall()
    ]


# ── PR creation ───────────────────────────────────────────────────────────────


class CreatePrBody(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    draft: bool = False


@router.post("/{conversation_id}/create-pr")
async def create_pull_request(
    conversation_id: uuid.UUID,
    pr_body: CreatePrBody,
    current: Annotated[User, Depends(get_authenticated_user)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Cria um Pull Request no GitHub a partir do branch actual do worktree.

    Requer GITHUB_TOKEN configurado no ambiente.
    """
    import os

    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GITHUB_TOKEN não configurado.",
        )

    # Get worktree + repo info
    row = await db.execute(
        text(
            """
            SELECT cs.worktree_path, c.base_branch, re.slug AS env_slug, re.repo_url
            FROM conversations c
            LEFT JOIN cappy_sessions cs ON cs.chat_id = c.id::text
            LEFT JOIN repo_environments re ON re.id = c.environment_id
            WHERE c.id = :cid AND c.user_id = :uid
            """
        ),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    conv = row.fetchone()
    if not conv or not conv.worktree_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversa ou worktree não encontrado.",
        )

    # Get current branch from worktree
    env_row = await db.execute(
        text("SELECT container_id FROM cappy_env_containers WHERE env_slug = :slug"),
        {"slug": conv.env_slug},
    )
    env = env_row.fetchone()
    if not env:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ambiente não encontrado.")

    try:
        import docker
        client = docker.from_env()
        container = client.containers.get(env.container_id)
        exit_code, output = container.exec_run(
            ["git", "-C", conv.worktree_path, "rev-parse", "--abbrev-ref", "HEAD"]
        )
        head_branch = output.decode("utf-8", errors="replace").strip() if output else ""
        if exit_code != 0 or not head_branch:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Não foi possível determinar o branch actual.",
            )

        # Push branch
        container.exec_run(["git", "-C", conv.worktree_path, "push", "--set-upstream", "origin", head_branch])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro ao obter branch: {exc}",
        ) from exc

    # Parse owner/repo from repo_url
    import re
    m = re.search(r"github\.com[:/](.+?/.+?)(?:\.git)?$", conv.repo_url or "")
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL do repositório não é um repo GitHub válido.",
        )
    owner_repo = m.group(1)

    base = conv.base_branch or "main"
    pr_title = pr_body.title or f"Agent changes from branch {head_branch}"
    pr_description = pr_body.body or f"Changes made by CappyCloud agent in conversation {conversation_id}."

    import httpx
    async with httpx.AsyncClient() as client_http:
        resp = await client_http.post(
            f"https://api.github.com/repos/{owner_repo}/pulls",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
            },
            json={
                "title": pr_title,
                "body": pr_description,
                "head": head_branch,
                "base": base,
                "draft": pr_body.draft,
            },
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API error {resp.status_code}: {resp.text[:500]}",
        )

    data = resp.json()
    pr_url = data.get("html_url", "")
    pr_number = data.get("number")

    # Store PR reference on the conversation
    await db.execute(
        text(
            "UPDATE conversations SET github_pr_number = :num, github_repo_slug = :slug "
            "WHERE id = :cid"
        ),
        {"num": pr_number, "slug": owner_repo, "cid": str(conversation_id)},
    )
    await db.commit()

    return {"pr_url": pr_url, "pr_number": pr_number, "head_branch": head_branch}


# ── PR subscriptions (auto-fix) ───────────────────────────────────────────────


@router.post("/{conversation_id}/pr-subscriptions", status_code=status.HTTP_201_CREATED)
async def create_pr_subscription(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Activa auto-fix para o PR associado a esta conversa."""
    # Verify ownership + get PR info
    row = await db.execute(
        text(
            "SELECT github_pr_number, github_repo_slug FROM conversations "
            "WHERE id = :cid AND user_id = :uid"
        ),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    conv = row.fetchone()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
    if not conv.github_pr_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversa não tem PR associado. Crie um PR primeiro.",
        )

    import uuid as _uuid
    sub_id = str(_uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO pr_subscriptions (id, conversation_id, repo_slug, pr_number, auto_fix_enabled) "
            "VALUES (:id, :cid, :slug, :num, TRUE)"
        ),
        {
            "id": sub_id,
            "cid": str(conversation_id),
            "slug": conv.github_repo_slug,
            "num": conv.github_pr_number,
        },
    )
    await db.commit()
    return {
        "id": sub_id,
        "conversation_id": str(conversation_id),
        "pr_number": conv.github_pr_number,
        "repo_slug": conv.github_repo_slug,
        "auto_fix_enabled": True,
    }
