"""Testes unitários para entidades de domínio."""

import uuid
from datetime import datetime

from app.domain.entities import Conversation, Message, User


class TestUser:
    def test_created_with_defaults(self) -> None:
        user = User(id=uuid.uuid4(), email="a@b.com", hashed_password="x")
        assert isinstance(user.created_at, datetime)

    def test_fields_accessible(self) -> None:
        uid = uuid.uuid4()
        user = User(id=uid, email="test@test.com", hashed_password="hashed")
        assert user.id == uid
        assert user.email == "test@test.com"
        assert user.hashed_password == "hashed"


class TestConversation:
    def test_created_with_defaults(self) -> None:
        conv = Conversation(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            title="Nova conversa",
        )
        assert isinstance(conv.created_at, datetime)
        assert isinstance(conv.updated_at, datetime)

    def test_title_stored(self) -> None:
        conv = Conversation(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Meu chat")
        assert conv.title == "Meu chat"


class TestMessage:
    def test_roles_stored(self) -> None:
        for role in ("user", "assistant", "system"):
            msg = Message(
                id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                role=role,
                content="Olá",
            )
            assert msg.role == role

    def test_content_stored(self) -> None:
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role="user",
            content="Conteúdo da mensagem",
        )
        assert msg.content == "Conteúdo da mensagem"
