"""Testes mutation-resistant para _stream_helpers.

Cobertura focada em propagação de ``confluence_url``/``confluence_space``
do banco para o pipeline do agente. Asserts pontuais e ambos os ramos
das condicionais — qualquer mutação que troque ``if confluence_url`` por
``if not confluence_url`` (ou que esqueça de propagar ``space``) deve fazer
ao menos um teste falhar.

Ver docs/AGENT_RULES.md §6.1.
"""

from __future__ import annotations

import uuid

import pytest
from app.application.use_cases._stream_helpers import (
    build_pipeline_body,
    enrich_repos_for_pipeline,
    ensure_repo_ids,
)
from app.domain.entities import Conversation, Repository
from app.domain.value_objects import PermissionMode

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


# ── enrich_repos_for_pipeline ──────────────────────────────────────────────


async def test_enrich_propagates_url_and_space_when_both_configured() -> None:
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(
        confluence_url="https://docs.example.com/wiki",
        confluence_space="FRONTEND",
    )
    repo_store.add(repo)

    enriched = await enrich_repos_for_pipeline(
        repo_store, [{"slug": "alpha", "repo_id": str(repo.id)}]
    )

    assert len(enriched) == 1
    assert enriched[0]["confluence_url"] == "https://docs.example.com/wiki"
    assert enriched[0]["confluence_space"] == "FRONTEND"


async def test_enrich_propagates_labels_when_url_configured() -> None:
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(
        confluence_url="https://docs.example.com/wiki",
        confluence_space="Frontend",
        confluence_labels=["react", "react-dom"],
    )
    repo_store.add(repo)

    enriched = await enrich_repos_for_pipeline(
        repo_store, [{"slug": "alpha", "repo_id": str(repo.id)}]
    )

    assert enriched[0]["confluence_labels"] == ["react", "react-dom"]


async def test_enrich_overwrites_clone_url_with_authenticated_version() -> None:
    """enrich precisa substituir clone_url pela versão com PAT (não vazio, não None)."""
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(slug="alpha")
    repo_store.add(repo)

    enriched = await enrich_repos_for_pipeline(
        repo_store,
        [{"slug": "alpha", "repo_id": str(repo.id), "clone_url": "https://git.example/alpha.git"}],
    )

    # A chave correta é "clone_url" (não "CLONE_URL", não "XXclone_urlXX").
    assert "clone_url" in enriched[0]
    # O valor não é None nem string vazia.
    assert enriched[0]["clone_url"]
    # O valor contém o token injetado (vem do fake autenticado).
    assert "pat:fake-token" in enriched[0]["clone_url"]
    # E é diferente do clone_url original do dict de entrada.
    assert enriched[0]["clone_url"] != "https://git.example/alpha.git"


async def test_enrich_omits_space_when_url_empty() -> None:
    """Space órfão (sem URL) não vaza pro pipeline."""
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(confluence_url="", confluence_space="ORPHAN", confluence_labels=["react"])
    repo_store.add(repo)

    enriched = await enrich_repos_for_pipeline(
        repo_store, [{"slug": "alpha", "repo_id": str(repo.id)}]
    )

    assert "confluence_url" not in enriched[0]
    assert "confluence_space" not in enriched[0]
    assert "confluence_labels" not in enriched[0]


async def test_enrich_emits_url_but_not_space_when_only_url_configured() -> None:
    """URL sem space: emite confluence_url, NÃO emite confluence_space."""
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(confluence_url="https://docs.example.com/wiki")
    repo_store.add(repo)

    enriched = await enrich_repos_for_pipeline(
        repo_store, [{"slug": "alpha", "repo_id": str(repo.id)}]
    )

    assert enriched[0]["confluence_url"] == "https://docs.example.com/wiki"
    assert "confluence_space" not in enriched[0]


async def test_enrich_preserves_other_keys_in_repo_dict() -> None:
    """Enrich não pode apagar nem sobrescrever campos pré-existentes do dict de repo."""
    repo_store = InMemoryRepositoryRepository()
    repo = _repo(confluence_url="https://docs.example.com/wiki", confluence_space="FRONTEND")
    repo_store.add(repo)

    enriched = await enrich_repos_for_pipeline(
        repo_store,
        [
            {
                "slug": "alpha",
                "repo_id": str(repo.id),
                "alias": "alpha-main",
                "branch_name": "cappy/alpha/abc",
                "worktree_path": "/repos/sessions/abc/alpha",
            }
        ],
    )

    assert enriched[0]["alias"] == "alpha-main"
    assert enriched[0]["branch_name"] == "cappy/alpha/abc"
    assert enriched[0]["worktree_path"] == "/repos/sessions/abc/alpha"


async def test_enrich_returns_repos_unchanged_when_no_port() -> None:
    enriched = await enrich_repos_for_pipeline(None, [{"slug": "x"}])
    assert enriched == [{"slug": "x"}]


async def test_enrich_skips_repo_without_repo_id() -> None:
    """Sem repo_id, não há lookup; dict passa sem confluence_*."""
    repo_store = InMemoryRepositoryRepository()
    enriched = await enrich_repos_for_pipeline(repo_store, [{"slug": "alpha"}])
    assert enriched == [{"slug": "alpha"}]


async def test_enrich_swallows_invalid_uuid_repo_id() -> None:
    """repo_id não-UUID não pode quebrar o pipeline — campo extra é simplesmente ignorado."""
    repo_store = InMemoryRepositoryRepository()
    enriched = await enrich_repos_for_pipeline(
        repo_store, [{"slug": "alpha", "repo_id": "not-a-uuid"}]
    )
    assert "confluence_url" not in enriched[0]
    assert "confluence_space" not in enriched[0]
    assert enriched[0]["slug"] == "alpha"


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


# ── build_pipeline_body ───────────────────────────────────────────────────


async def test_build_pipeline_body_includes_conversation_permission_mode() -> None:
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="t",
        permission_mode=PermissionMode.AUTO.value,
    )

    body = build_pipeline_body(
        conv,
        enriched_repos=[],
        user_id=conv.user_id,
        cursor=None,
        override_model=None,
        attachments_payload=None,
    )

    assert body["permission_mode"] == PermissionMode.AUTO.value


async def test_build_pipeline_body_defaults_legacy_permission_mode() -> None:
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="t",
        permission_mode="legacy-unknown",
    )

    body = build_pipeline_body(
        conv,
        enriched_repos=[],
        user_id=conv.user_id,
        cursor=None,
        override_model=None,
        attachments_payload=None,
    )

    assert body["permission_mode"] == PermissionMode.BYPASS_PERMISSIONS.value
