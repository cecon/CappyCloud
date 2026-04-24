"""Unit tests for conversation use cases."""

import uuid

import pytest
from app.application.use_cases.conversations import (
    CreateConversation,
    ListConversations,
    ListMessages,
    StreamMessage,
)
from app.domain.entities import Repository

from tests.conftest import (
    FakeAgent,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
    InMemoryRepositoryRepository,
    InMemoryUserAgentProfileRepository,
)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def conv_repo() -> InMemoryConversationRepository:
    return InMemoryConversationRepository()


@pytest.fixture
def msg_repo() -> InMemoryMessageRepository:
    return InMemoryMessageRepository()


@pytest.fixture
def agent() -> FakeAgent:
    return FakeAgent()


class TestListConversations:
    async def test_empty_list_for_new_user(
        self, conv_repo: InMemoryConversationRepository, user_id: uuid.UUID
    ) -> None:
        uc = ListConversations(conv_repo)
        assert await uc.execute(user_id) == []

    async def test_returns_only_user_conversations(
        self, conv_repo: InMemoryConversationRepository
    ) -> None:
        uid_a = uuid.uuid4()
        uid_b = uuid.uuid4()
        create = CreateConversation(conv_repo)
        await create.execute(uid_a, "Chat A")
        await create.execute(uid_b, "Chat B")

        result = await ListConversations(conv_repo).execute(uid_a)
        assert len(result) == 1
        assert result[0].title == "Chat A"


class TestCreateConversation:
    async def test_creates_with_given_title(
        self, conv_repo: InMemoryConversationRepository, user_id: uuid.UUID
    ) -> None:
        uc = CreateConversation(conv_repo)
        conv = await uc.execute(user_id, "Meu chat")
        assert conv.title == "Meu chat"
        assert conv.user_id == user_id

    async def test_defaults_title_when_none(
        self, conv_repo: InMemoryConversationRepository, user_id: uuid.UUID
    ) -> None:
        uc = CreateConversation(conv_repo)
        conv = await uc.execute(user_id)
        assert conv.title == "Nova conversa"

    async def test_assigns_uuid(
        self, conv_repo: InMemoryConversationRepository, user_id: uuid.UUID
    ) -> None:
        uc = CreateConversation(conv_repo)
        conv = await uc.execute(user_id)
        assert isinstance(conv.id, uuid.UUID)

    async def test_resolves_repo_slug_to_repo_id(
        self,
        conv_repo: InMemoryConversationRepository,
        user_id: uuid.UUID,
    ) -> None:
        repo_catalog = InMemoryRepositoryRepository()
        repo = Repository(
            id=uuid.uuid4(),
            slug="autosystem",
            name="autosystem",
            clone_url="https://example.com/autosystem.git",
        )
        repo_catalog.add(repo)
        uc = CreateConversation(conv_repo, repo_catalog)

        conv = await uc.execute(user_id, repos=[{"slug": "autosystem"}])

        assert len(conv.repos) == 1
        assert conv.repos[0]["slug"] == "autosystem"
        assert conv.repos[0]["repo_id"] == str(repo.id)

    async def test_repo_id_is_none_for_unknown_slug(
        self,
        conv_repo: InMemoryConversationRepository,
        user_id: uuid.UUID,
    ) -> None:
        repo_catalog = InMemoryRepositoryRepository()
        uc = CreateConversation(conv_repo, repo_catalog)

        conv = await uc.execute(user_id, repos=[{"slug": "nao-existe"}])

        assert conv.repos[0]["repo_id"] is None

    async def test_uses_user_default_agent_when_not_provided(
        self,
        conv_repo: InMemoryConversationRepository,
        user_id: uuid.UUID,
    ) -> None:
        default_agent_id = uuid.uuid4()
        profiles = InMemoryUserAgentProfileRepository()
        profiles.set_default(user_id, default_agent_id)
        uc = CreateConversation(conv_repo, user_agent_profiles=profiles)

        conv = await uc.execute(user_id)

        assert conv.agent_id == default_agent_id

    async def test_explicit_agent_overrides_user_default(
        self,
        conv_repo: InMemoryConversationRepository,
        user_id: uuid.UUID,
    ) -> None:
        default_agent_id = uuid.uuid4()
        explicit_agent_id = uuid.uuid4()
        profiles = InMemoryUserAgentProfileRepository()
        profiles.set_default(user_id, default_agent_id)
        uc = CreateConversation(conv_repo, user_agent_profiles=profiles)

        conv = await uc.execute(user_id, agent_id=explicit_agent_id)

        assert conv.agent_id == explicit_agent_id


class TestListMessages:
    async def test_raises_when_conversation_not_found(
        self,
        conv_repo: InMemoryConversationRepository,
        msg_repo: InMemoryMessageRepository,
        user_id: uuid.UUID,
    ) -> None:
        uc = ListMessages(conv_repo, msg_repo)
        with pytest.raises(LookupError, match="não encontrada"):
            await uc.execute(uuid.uuid4(), user_id)

    async def test_raises_when_wrong_owner(
        self,
        conv_repo: InMemoryConversationRepository,
        msg_repo: InMemoryMessageRepository,
    ) -> None:
        owner = uuid.uuid4()
        other = uuid.uuid4()
        create = CreateConversation(conv_repo)
        conv = await create.execute(owner, "Owner's chat")
        uc = ListMessages(conv_repo, msg_repo)
        with pytest.raises(LookupError):
            await uc.execute(conv.id, other)

    async def test_returns_messages_in_order(
        self,
        conv_repo: InMemoryConversationRepository,
        msg_repo: InMemoryMessageRepository,
        user_id: uuid.UUID,
    ) -> None:
        create = CreateConversation(conv_repo)
        conv = await create.execute(user_id, "Chat")
        stream_uc = StreamMessage(conv_repo, msg_repo, FakeAgent())
        gen = await stream_uc.execute(conv.id, user_id, "Olá")
        async for _ in gen:
            pass  # drain generator

        msgs = await ListMessages(conv_repo, msg_repo).execute(conv.id, user_id)
        assert msgs[0].role == "user"
        assert msgs[0].content == "Olá"


class TestStreamMessage:
    async def test_raises_when_not_owner(
        self,
        conv_repo: InMemoryConversationRepository,
        msg_repo: InMemoryMessageRepository,
        agent: FakeAgent,
        user_id: uuid.UUID,
    ) -> None:
        uc = StreamMessage(conv_repo, msg_repo, agent)
        with pytest.raises(LookupError):
            await uc.execute(uuid.uuid4(), user_id, "mensagem")

    async def test_yields_bytes(
        self,
        conv_repo: InMemoryConversationRepository,
        msg_repo: InMemoryMessageRepository,
        agent: FakeAgent,
        user_id: uuid.UUID,
    ) -> None:
        conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
        uc = StreamMessage(conv_repo, msg_repo, agent)
        stream = await uc.execute(conv.id, user_id, "Olá agente")
        chunks = [c async for c in stream]
        assert any(isinstance(c, bytes) for c in chunks)
        combined = b"".join(chunks).decode()
        assert "text" in combined

    async def test_auto_titles_default_conversation(
        self,
        conv_repo: InMemoryConversationRepository,
        msg_repo: InMemoryMessageRepository,
        agent: FakeAgent,
        user_id: uuid.UUID,
    ) -> None:
        conv = await CreateConversation(conv_repo).execute(user_id)
        assert conv.title == "Nova conversa"

        uc = StreamMessage(conv_repo, msg_repo, agent)
        stream = await uc.execute(conv.id, user_id, "Primeira mensagem longa")
        async for _ in stream:
            pass  # drain

        updated = await conv_repo.get(conv.id, user_id)
        assert updated is not None
        assert updated.title == "Primeira mensagem longa"

    async def test_saves_assistant_message_after_stream(
        self,
        conv_repo: InMemoryConversationRepository,
        msg_repo: InMemoryMessageRepository,
        user_id: uuid.UUID,
    ) -> None:
        conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
        uc = StreamMessage(conv_repo, msg_repo, FakeAgent("Resposta do bot"))
        stream = await uc.execute(conv.id, user_id, "Pergunta")
        async for _ in stream:
            pass  # drain all chunks

        msgs = await msg_repo.list_by_conversation(conv.id)
        roles = [m.role for m in msgs]
        assert "user" in roles
        assert "assistant" in roles
        assistant_msg = next(m for m in msgs if m.role == "assistant")
        assert assistant_msg.content == "Resposta do bot"
