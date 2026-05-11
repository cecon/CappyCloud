"""Expressões SQL partilhadas para resolver caminhos de worktree no sandbox.

Convém com `CreateConversation`: ``short_id = conv_id.hex[:12]``,
``session_root = /repos/sessions/{short_id}``,
``worktree_path = /repos/sessions/{short_id}/{alias}``.
"""

from __future__ import annotations

import uuid
from typing import Any

# Fragmento SELECT (sem FROM/WHERE) — usar com alias `c` = conversations, `cs` = cappy_sessions
WORKTREE_PATH_COLUMNS = """
  COALESCE(
    cs.repos->0->>'worktree_path',
    c.repos->0->>'worktree_path',
    CASE
      WHEN COALESCE(jsonb_array_length(COALESCE(c.repos, '[]'::jsonb)), 0) > 0 THEN
        '/repos/sessions/' || substr(replace(c.id::text, '-', ''), 1, 12) || '/' ||
        COALESCE(
          NULLIF(c.repos->0->>'alias', ''),
          NULLIF(c.repos->0->>'slug', ''),
          'repo'
        )
      ELSE NULL
    END,
    '/repos/sessions/' || substr(replace(c.id::text, '-', ''), 1, 12)
  ) AS worktree_path,
  COALESCE(
    cs.session_root,
    c.session_root,
    '/repos/sessions/' || substr(replace(c.id::text, '-', ''), 1, 12)
  ) AS session_root,
  COALESCE(
    cs.repos->0->>'base_branch',
    c.repos->0->>'base_branch',
    'main'
  ) AS base_branch
"""

WORKTREE_FROM_CONVERSATION = f"""
SELECT {WORKTREE_PATH_COLUMNS.strip()}
FROM conversations c
LEFT JOIN cappy_sessions cs ON cs.chat_id = c.id::text
WHERE c.id = :cid AND c.user_id = :uid
"""

# Igual ao anterior + clone_url para criar PR (slug da BD ou da conversa).
CREATE_PR_FROM_CONVERSATION = f"""
SELECT {WORKTREE_PATH_COLUMNS.strip()},
  r.clone_url AS repo_url
FROM conversations c
LEFT JOIN cappy_sessions cs ON cs.chat_id = c.id::text
LEFT JOIN repositories r ON r.slug = COALESCE(cs.repos->0->>'slug', c.repos->0->>'slug')
WHERE c.id = :cid AND c.user_id = :uid
"""


def _strip_or_none(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def resolve_git_paths_from_worktree_row(
    row: Any,
    conversation_id: uuid.UUID,
) -> tuple[str, str, str]:
    """Extrai (worktree para git, session_root, base_branch) da linha do WORKTREE_FROM_CONVERSATION.

    Usa **índices posicionais** (``row[0]``…``row[2]``), porque com ``text()`` alguns
    drivers não expõem ``row.worktree_path`` como atributo e aparecia sempre vazio.

    Garante pelo menos ``/repos/sessions/<hex12>``, igual ao ``CreateConversation``.
    """
    short_root = f"/repos/sessions/{conversation_id.hex[:12]}"
    if len(row) < 3:
        return short_root, short_root, "main"

    wt = _strip_or_none(row[0])
    sr = _strip_or_none(row[1])
    bb = _strip_or_none(row[2]) if len(row) > 2 else None
    base_branch = bb or "main"

    worktree = wt or sr or short_root
    session_root = sr or short_root
    return worktree, session_root, base_branch


def repo_url_from_create_pr_row(row: Any) -> str | None:
    """Clone URL (4.ª coluna de CREATE_PR_FROM_CONVERSATION)."""
    if row is None or len(row) < 4:
        return None
    return _strip_or_none(row[3])
