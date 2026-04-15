"""FastAPI dependency injection wiring — composition root for HTTP adapters.

All use case objects are assembled here using FastAPI's Depends() system.
No business logic lives in this file.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.secondary.persistence.sqlalchemy_conversation_repo import (
    SQLAlchemyConversationRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_message_repo import (
    SQLAlchemyMessageRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_repo_env_repo import (
    SQLAlchemyRepoEnvironmentRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_user_repo import (
    SQLAlchemyUserRepository,
)
from app.application.use_cases.auth import GetCurrentUser, LoginUser, RegisterUser
from app.application.use_cases.conversations import (
    CreateConversation,
    CreateRepoEnvironment,
    DeleteRepoEnvironment,
    ListConversations,
    ListMessages,
    ListRepoEnvironments,
    StreamMessage,
)
from app.domain.entities import User
from app.infrastructure.database import get_db
from app.ports.agent import AgentPort
from app.ports.repositories import (
    ConversationRepository,
    MessageRepository,
    RepoEnvironmentRepository,
    UserRepository,
)
from app.ports.services import PasswordService, TokenService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ---------------------------------------------------------------------------
# Infrastructure dependencies
# ---------------------------------------------------------------------------


async def get_db_session(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncSession:
    return session


# ---------------------------------------------------------------------------
# Repository dependencies
# ---------------------------------------------------------------------------


def get_user_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepository:
    return SQLAlchemyUserRepository(session)


def get_conv_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationRepository:
    return SQLAlchemyConversationRepository(session)


def get_msg_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MessageRepository:
    return SQLAlchemyMessageRepository(session)


def get_repo_env_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RepoEnvironmentRepository:
    return SQLAlchemyRepoEnvironmentRepository(session)


# ---------------------------------------------------------------------------
# Service dependencies
# ---------------------------------------------------------------------------


def get_password_service() -> PasswordService:
    from app.infrastructure.security import BcryptPasswordService

    return BcryptPasswordService()


def get_token_service() -> TokenService:
    from app.infrastructure.security import JWTTokenService

    return JWTTokenService()


def get_agent(request: Request) -> AgentPort:
    """Retrieve the Pipeline adapter stored on app.state at startup."""
    return request.app.state.agent  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Use case dependencies
# ---------------------------------------------------------------------------


def get_register_uc(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
) -> RegisterUser:
    return RegisterUser(users, passwords)


def get_login_uc(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> LoginUser:
    return LoginUser(users, passwords, tokens)


def get_current_user_uc(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> GetCurrentUser:
    return GetCurrentUser(users, tokens)


async def get_authenticated_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    uc: Annotated[GetCurrentUser, Depends(get_current_user_uc)],
) -> User:
    """FastAPI dependency that resolves the current authenticated user."""
    try:
        return await uc.execute(token)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_list_convs_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
) -> ListConversations:
    return ListConversations(convs)


def get_create_conv_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
) -> CreateConversation:
    return CreateConversation(convs)


def get_list_msgs_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
    msgs: Annotated[MessageRepository, Depends(get_msg_repo)],
) -> ListMessages:
    return ListMessages(convs, msgs)


def get_stream_msg_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
    msgs: Annotated[MessageRepository, Depends(get_msg_repo)],
    agent: Annotated[AgentPort, Depends(get_agent)],
) -> StreamMessage:
    return StreamMessage(convs, msgs, agent)


def get_list_repo_envs_uc(
    repo_envs: Annotated[RepoEnvironmentRepository, Depends(get_repo_env_repo)],
) -> ListRepoEnvironments:
    return ListRepoEnvironments(repo_envs)


def get_create_repo_env_uc(
    repo_envs: Annotated[RepoEnvironmentRepository, Depends(get_repo_env_repo)],
) -> CreateRepoEnvironment:
    return CreateRepoEnvironment(repo_envs)


def get_delete_repo_env_uc(
    repo_envs: Annotated[RepoEnvironmentRepository, Depends(get_repo_env_repo)],
    agent: Annotated[AgentPort, Depends(get_agent)],
) -> DeleteRepoEnvironment:
    return DeleteRepoEnvironment(repo_envs, agent)
