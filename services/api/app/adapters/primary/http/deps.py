"""FastAPI dependency injection wiring — composition root for HTTP adapters.

All use case objects are assembled here using FastAPI's Depends() system.
No business logic lives in this file.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.secondary.persistence.sqlalchemy_ai_model_access_policy import (
    SQLAlchemyAiModelAccessPolicy,
)
from app.adapters.secondary.persistence.sqlalchemy_mcp_repo import (
    SQLAlchemyMcpRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_message_repo import (
    SQLAlchemyMessageRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_repo_env_repo import (
    SQLAlchemyRepoEnvironmentRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_repository_repo import (
    SQLAlchemyRepositoryRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_user_access_repo import (
    SQLAlchemyUserRepositoryAccessRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_user_mcp_repo import (
    SQLAlchemyUserMcpServerRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_user_repo import (
    SQLAlchemyUserRepository,
)
from app.adapters.secondary.repository_mcp_tool_gateway import (
    SQLAlchemyRepositoryMcpToolGateway,
)
from app.application.use_cases.ai_models import ListAiModels
from app.application.use_cases.auth import ChangePassword, GetCurrentUser, LoginUser, RegisterUser
from app.application.use_cases.conversations import (
    CreateConversation,
    ListConversations,
    ListMessages,
    StreamMessage,
)
from app.application.use_cases.repo_environments import (
    CreateRepoEnvironment,
    DeleteRepoEnvironment,
    ListRepoEnvironments,
)
from app.domain.entities import User, UserRole
from app.ports.agent import AgentPort
from app.ports.mcp_repository import McpServerRepository, UserMcpServerRepository
from app.ports.repositories import (
    AiModelCapabilityLookup,
    AttachmentRepository,
    ConversationRepository,
    MessageRepository,
    RepoEnvironmentRepository,
    RepositoryRepository,
    UserRepository,
)
from app.ports.repository_mcp import RepositoryMcpToolGateway
from app.ports.services import AttachmentStorage, ModelCatalogService, PasswordService, TokenService
from app.ports.user_access import AiModelAccessPolicy, UserRepositoryAccessRepository

from . import deps_attachments as _attach_deps
from .deps_base import get_conv_repo, get_db_session  # re-export

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ---------------------------------------------------------------------------
# Infrastructure dependencies
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Repository dependencies
# ---------------------------------------------------------------------------


def get_user_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepository:
    return SQLAlchemyUserRepository(session)


def get_msg_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MessageRepository:
    return SQLAlchemyMessageRepository(session)


def get_repo_env_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RepoEnvironmentRepository:
    return SQLAlchemyRepoEnvironmentRepository(session)


def get_repository_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RepositoryRepository:
    return SQLAlchemyRepositoryRepository(session)


def get_ai_model_access_policy(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiModelAccessPolicy:
    return SQLAlchemyAiModelAccessPolicy(session)


def get_user_repository_access_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepositoryAccessRepository:
    return SQLAlchemyUserRepositoryAccessRepository(session)


def get_mcp_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> McpServerRepository:
    return SQLAlchemyMcpRepository(session)


def get_user_mcp_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserMcpServerRepository:
    return SQLAlchemyUserMcpServerRepository(session)


def get_repository_mcp_tool_gateway(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RepositoryMcpToolGateway:
    return SQLAlchemyRepositoryMcpToolGateway(session)


# ---------------------------------------------------------------------------
# Service dependencies
# ---------------------------------------------------------------------------


def get_password_service() -> PasswordService:
    from app.infrastructure.security import BcryptPasswordService

    return BcryptPasswordService()


def get_token_service() -> TokenService:
    from app.infrastructure.security import JWTTokenService

    return JWTTokenService()


def get_model_catalog_service() -> ModelCatalogService:
    from app.adapters.secondary.openrouter_catalog import OpenRouterModelCatalog

    return OpenRouterModelCatalog()


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


def get_change_password_uc(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
) -> ChangePassword:
    return ChangePassword(users, passwords)


def get_list_ai_models_uc(
    catalog: Annotated[ModelCatalogService, Depends(get_model_catalog_service)],
) -> ListAiModels:
    return ListAiModels(catalog)


async def get_authenticated_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    uc: Annotated[GetCurrentUser, Depends(get_current_user_uc)],
) -> User:
    """FastAPI dependency that resolves the current authenticated user."""
    try:
        user = await uc.execute(token)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if user.must_change_password and request.url.path not in {
        "/api/auth/me",
        "/api/auth/change-password",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Troque a senha inicial antes de continuar.",
        )
    return user


def require_role(required: UserRole):
    """FastAPI dependency factory que exige um papel específico.

    Retorna uma dependência que devolve o utilizador autenticado se o papel
    bater (ou se for :attr:`UserRole.ADMIN`, que tem acesso a tudo). Caso
    contrário levanta 403. ADR-005 documenta a regra: ``ADMIN`` ignora o
    requisito e sempre passa.

    Uso::

        @router.post("/admin/...", dependencies=[Depends(require_role(UserRole.ADMIN))])
        async def admin_only(...): ...

    Ou para receber o utilizador resolvido::

        async def admin_only(user: Annotated[User, Depends(require_role(UserRole.ADMIN))]): ...
    """

    async def _dep(
        current: Annotated[User, Depends(get_authenticated_user)],
    ) -> User:
        if current.role is UserRole.ADMIN or current.role is required:
            return current
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão insuficiente.",
        )

    return _dep


async def require_super_admin(
    current: Annotated[User, Depends(get_authenticated_user)],
) -> User:
    """Exige ADMIN com marcação ``is_super_admin`` para configuração sistêmica."""
    if current.role is UserRole.ADMIN and current.is_super_admin:
        return current
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permissão de super admin necessária.",
    )


def get_list_convs_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
) -> ListConversations:
    return ListConversations(convs)


def get_create_conv_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
    repos: Annotated[RepositoryRepository, Depends(get_repository_repo)],
) -> CreateConversation:
    return CreateConversation(convs, repos)


def get_list_msgs_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
    msgs: Annotated[MessageRepository, Depends(get_msg_repo)],
) -> ListMessages:
    return ListMessages(convs, msgs)


def get_stream_msg_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
    msgs: Annotated[MessageRepository, Depends(get_msg_repo)],
    agent: Annotated[AgentPort, Depends(get_agent)],
    repos: Annotated[RepositoryRepository, Depends(get_repository_repo)],
    attachments: Annotated[AttachmentRepository, Depends(_attach_deps.get_attachment_repo)],
    storage: Annotated[AttachmentStorage, Depends(_attach_deps.get_attachment_storage)],
    model_caps: Annotated[AiModelCapabilityLookup, Depends(_attach_deps.get_ai_model_caps)],
    model_access: Annotated[AiModelAccessPolicy, Depends(get_ai_model_access_policy)],
) -> StreamMessage:
    return StreamMessage(
        convs,
        msgs,
        agent,
        repos,
        attachments=attachments,
        attachment_storage=storage,
        model_caps=model_caps,
        model_access=model_access,
    )


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
) -> DeleteRepoEnvironment:
    return DeleteRepoEnvironment(repo_envs)
