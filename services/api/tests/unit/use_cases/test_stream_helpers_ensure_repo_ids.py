"""Testes mutation-resistant para ensure_repo_ids (ver docs/AGENT_RULES.md §6.1)."""

from __future__ import annotations

import uuid

import pytest
from app.application.use_cases._stream_helpers import (
    ensure_repo_ids,
)
from app.domain.entities import Conversation, Repository

from tests.conftest import InMemoryConversationRepository, InMemoryRepositoryRepository

pytestmark = pytest.mark.asyncio


def _repo(
    *,
    slug: str = "alpha",
    confluence_url: str = "",
    confluence_space: str = "",
    confluence_labels: list[str] | None = None,
) -> Repository:
    return Repository(
        id=uuid.uuid4(),
        slug=slug,
        name=f"{slug}-name",
        clone_url=f"https://git.example/{slug}.git",
        confluence_url=confluence_url,
        confluence_space=confluence_space,
        confluence_labels=confluence_labels or [],
    )


# ── ensure_repo_ids ────────────────────────────────────────────────────────


def _conv_with_slug(slug: str) -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="t",
        repos=[{"slug": slug}],
    )


class _SpyConversations(InMemoryConversationRepository):
    """Conta chamadas a ``update`` para detectar bugs em ``changed`` flag."""

    def __init__(self) -> None:
        super().__init__()
        self.update_calls = 0

    async def update(self, conversation: Conversation) -> Conversation:
        self.update_calls += 1
        return await super().update(conversation)


async def test_ensure_repo_ids_sets_url_and_space_when_both_configured() -> None:
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(confluence_url="https://docs.example.com/wiki", confluence_space="FRONTEND")
    repo_store.add(repo)
    conv = _conv_with_slug("alpha")
    conv_store = InMemoryConversationRepository()
    await conv_store.save(conv)

    await ensure_repo_ids(repo_store, conv_store, conv)

    assert conv.repos[0]["repo_id"] == str(repo.id)
    assert conv.repos[0]["confluence_url"] == "https://docs.example.com/wiki"
    assert conv.repos[0]["confluence_space"] == "FRONTEND"


async def test_ensure_repo_ids_sets_labels_when_url_configured() -> None:
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(
        confluence_url="https://docs.example.com/wiki",
        confluence_space="Frontend",
        confluence_labels=["react", "react-dom"],
    )
    repo_store.add(repo)
    conv = _conv_with_slug("alpha")
    conv_store = InMemoryConversationRepository()
    await conv_store.save(conv)

    await ensure_repo_ids(repo_store, conv_store, conv)

    assert conv.repos[0]["confluence_labels"] == ["react", "react-dom"]


async def test_ensure_repo_ids_no_confluence_keys_when_url_empty() -> None:
    """Repo cadastrado mas sem URL → não escreve confluence_* no dict."""
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(confluence_url="", confluence_space="ORPHAN", confluence_labels=["react"])
    repo_store.add(repo)
    conv = _conv_with_slug("alpha")
    conv_store = InMemoryConversationRepository()
    await conv_store.save(conv)

    await ensure_repo_ids(repo_store, conv_store, conv)

    assert conv.repos[0]["repo_id"] == str(repo.id)
    assert "confluence_url" not in conv.repos[0]
    assert "confluence_space" not in conv.repos[0]
    assert "confluence_labels" not in conv.repos[0]


async def test_ensure_repo_ids_url_only_when_space_empty() -> None:
    """URL sem space → escreve só confluence_url."""
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(confluence_url="https://docs.example.com/wiki", confluence_space="")
    repo_store.add(repo)
    conv = _conv_with_slug("alpha")
    conv_store = InMemoryConversationRepository()
    await conv_store.save(conv)

    await ensure_repo_ids(repo_store, conv_store, conv)

    assert conv.repos[0]["confluence_url"] == "https://docs.example.com/wiki"
    assert "confluence_space" not in conv.repos[0]


async def test_ensure_repo_ids_noop_when_repo_id_already_set() -> None:
    """Se o repo já tem repo_id, ensure_repo_ids não toca."""
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(confluence_url="https://docs.example.com/wiki", confluence_space="FRONTEND")
    repo_store.add(repo)
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="t",
        repos=[{"slug": "alpha", "repo_id": "preexisting-id"}],
    )
    conv_store = InMemoryConversationRepository()
    await conv_store.save(conv)

    await ensure_repo_ids(repo_store, conv_store, conv)

    assert conv.repos[0]["repo_id"] == "preexisting-id"
    assert "confluence_url" not in conv.repos[0]
    assert "confluence_space" not in conv.repos[0]


async def test_ensure_repo_ids_noop_when_port_missing() -> None:
    conv = _conv_with_slug("alpha")
    conv_store = InMemoryConversationRepository()
    await conv_store.save(conv)

    await ensure_repo_ids(None, conv_store, conv)

    assert "repo_id" not in conv.repos[0]


async def test_ensure_repo_ids_noop_when_no_repos() -> None:
    conv = Conversation(id=uuid.uuid4(), user_id=uuid.uuid4(), title="t", repos=[])
    repo_store = InMemoryRepositoryRepository()
    conv_store = InMemoryConversationRepository()
    await conv_store.save(conv)

    await ensure_repo_ids(repo_store, conv_store, conv)
    assert conv.repos == []


async def test_ensure_repo_ids_persists_exactly_once_when_change_happens() -> None:
    """changed=True deve disparar exatamente UM update — mata mutações em ``changed``."""
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(confluence_url="https://docs.example.com/wiki", confluence_space="FRONTEND")
    repo_store.add(repo)
    conv = _conv_with_slug("alpha")
    conv_store = _SpyConversations()
    await conv_store.save(conv)

    await ensure_repo_ids(repo_store, conv_store, conv)

    assert conv_store.update_calls == 1


async def test_ensure_repo_ids_does_not_persist_when_nothing_changes() -> None:
    """Sem mudança, ``conversations.update`` NÃO é chamado."""
    repo_store = InMemoryRepositoryRepository()
    # Repo já tem repo_id pré-existente — nada a resolver.
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="t",
        repos=[{"slug": "alpha", "repo_id": "preexisting"}],
    )
    conv_store = _SpyConversations()
    await conv_store.save(conv)

    await ensure_repo_ids(repo_store, conv_store, conv)

    assert conv_store.update_calls == 0


async def test_ensure_repo_ids_multi_repo_continues_past_already_resolved() -> None:
    """``continue`` deve pular um repo já resolvido SEM parar de processar os demais.

    Mata mutação ``continue → break`` no check de ``repo_id`` existente.
    """
    repo_store = InMemoryRepositoryRepository()
    repo_b = _repo(slug="beta", confluence_url="https://x.example/wiki", confluence_space="BETA")
    repo_store.add(repo_b)
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="t",
        repos=[
            {"slug": "alpha", "repo_id": "preexisting-alpha"},
            {"slug": "beta"},  # precisa ser resolvido
        ],
    )
    conv_store = _SpyConversations()
    await conv_store.save(conv)

    await ensure_repo_ids(repo_store, conv_store, conv)

    # O primeiro repo ficou intacto (já tinha repo_id).
    assert conv.repos[0]["repo_id"] == "preexisting-alpha"
    # O segundo repo foi resolvido — `continue` no primeiro NÃO parou o loop.
    assert conv.repos[1]["repo_id"] == str(repo_b.id)
    assert conv.repos[1]["confluence_url"] == "https://x.example/wiki"
    assert conv.repos[1]["confluence_space"] == "BETA"


async def test_ensure_repo_ids_multi_repo_continues_past_empty_slug() -> None:
    """``continue`` no slug vazio NÃO pode interromper o loop dos demais repos."""
    repo_store = InMemoryRepositoryRepository()
    repo_b = _repo(slug="beta")
    repo_store.add(repo_b)
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="t",
        repos=[
            {"slug": ""},  # slug vazio: pula
            {"slug": "beta"},
        ],
    )
    conv_store = _SpyConversations()
    await conv_store.save(conv)

    await ensure_repo_ids(repo_store, conv_store, conv)

    assert "repo_id" not in conv.repos[0]
    assert conv.repos[1]["repo_id"] == str(repo_b.id)
