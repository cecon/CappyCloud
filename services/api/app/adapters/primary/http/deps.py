"""FastAPI dependency injection wiring - composition root for HTTP adapters.

All use case objects are assembled here using FastAPI's Depends() system.
No business logic lives in this file.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
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
from app.adapters.secondary.persistence.sqlalchemy_model_profiles import (
    SQLAlchemyModelProfileLookup,
)
from app.adapters.secondary.persistence.sqlalchemy_repo_env_repo import (
    SQLAlchemyRepoEnvironmentRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_repository_repo import (
    SQLAlchemyRepositoryRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_sandbox_repo import SQLAlchemySandboxRepository
from app.adapters.secondary.persistence.sqlalchemy_user_access_repo import (
    SQLAlchemyUserRepositoryAccessRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_user_mcp_repo import (
    SQLAlchemyUserMcpServerRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_user_preferences_repo import (
    SQLAlchemyUserPreferencesRepository,
)
from app.adapters.secondary.persistence.sqlalchemy_user_workspace_repo import (
    SQLAlchemyUserRepositoryWorkspaceRepository,
)
from app.adapters.secondary.repository_mcp_tool_gateway import (
    SQLAlchemyRepositoryMcpToolGateway,
)
from app.adapters.secondary.sandbox_runtime.chat_commands import SandboxChatCommandRuntime
from app.adapters.secondary.sandbox_user_workspace_client import SandboxUserWorkspaceClient
from app.application.use_cases.ai_models import ListAiModels
from app.application.use_cases.chat_command_execution import ExecuteChatCommand
from app.application.use_cases.chat_commands import ListChatCommands
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
from app.application.use_cases.user_preferences import GetUserPreferences, UpdateUserPreferences
from app.application.use_cases.user_workspaces import (
    DeleteUserRepositoryWorkspace,
    EnsureUserRepositoryWorkspace,
    ListUserRepositoryWorkspaces,
)
from app.ports.agent import AgentPort
from app.ports.chat_commands import ChatCommandRuntimePort
from app.ports.mcp_repository import McpServerRepository, UserMcpServerRepository
from app.ports.model_profiles import ModelProfileLookupPort
from app.ports.repositories import (
    AiModelCapabilityLookup,
    AttachmentRepository,
    ConversationRepository,
    MessageRepository,
    RepoEnvironmentRepository,
    RepositoryRepository,
    SandboxRepository,
)
from app.ports.repository_mcp import RepositoryMcpToolGateway
from app.ports.services import AttachmentStorage, ModelCatalogService
from app.ports.user_access import AiModelAccessPolicy, UserRepositoryAccessRepository
from app.ports.user_preferences import UserPreferencesRepository
from app.ports.user_workspaces import UserRepositoryWorkspaceRepository

from . import deps_attachments as _attach_deps
from .deps_auth import (
    get_authenticated_user as get_authenticated_user,
)
from .deps_auth import (
    get_change_password_uc as get_change_password_uc,
)
from .deps_auth import (
    get_login_uc as get_login_uc,
)
from .deps_auth import (
    get_password_service as get_password_service,
)
from .deps_auth import (
    get_register_uc as get_register_uc,
)
from .deps_auth import (
    get_token_service as get_token_service,
)
from .deps_auth import (
    get_user_repo as get_user_repo,
)
from .deps_auth import (
    require_role as require_role,
)
from .deps_auth import (
    require_super_admin as require_super_admin,
)
from .deps_base import get_conv_repo, get_db_session  # re-export

# ---------------------------------------------------------------------------
# Infrastructure dependencies
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Repository dependencies
# ---------------------------------------------------------------------------


def get_user_preferences_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserPreferencesRepository:
    return SQLAlchemyUserPreferencesRepository(session)


def get_user_workspace_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepositoryWorkspaceRepository:
    return SQLAlchemyUserRepositoryWorkspaceRepository(session)


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


def get_sandbox_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SandboxRepository:
    return SQLAlchemySandboxRepository(session)


def get_ai_model_access_policy(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiModelAccessPolicy:
    return SQLAlchemyAiModelAccessPolicy(session)


def get_model_profile_lookup(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ModelProfileLookupPort:
    return SQLAlchemyModelProfileLookup(session)


def get_chat_command_runtime() -> ChatCommandRuntimePort:
    return SandboxChatCommandRuntime()


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


def get_model_catalog_service() -> ModelCatalogService:
    from app.adapters.secondary.openrouter_catalog import OpenRouterModelCatalog

    return OpenRouterModelCatalog()


def get_agent(request: Request) -> AgentPort:
    """Retrieve the Pipeline adapter stored on app.state at startup."""
    return request.app.state.agent  # type: ignore[no-any-return]


def get_sandbox_workspace_gateway() -> SandboxUserWorkspaceClient:
    return SandboxUserWorkspaceClient()


# ---------------------------------------------------------------------------
# Use case dependencies
# ---------------------------------------------------------------------------


def get_user_preferences_uc(
    preferences: Annotated[UserPreferencesRepository, Depends(get_user_preferences_repo)],
) -> GetUserPreferences:
    return GetUserPreferences(preferences)


def get_update_user_preferences_uc(
    preferences: Annotated[UserPreferencesRepository, Depends(get_user_preferences_repo)],
) -> UpdateUserPreferences:
    return UpdateUserPreferences(preferences)


def get_ensure_user_workspace_uc(
    workspaces: Annotated[UserRepositoryWorkspaceRepository, Depends(get_user_workspace_repo)],
    repos: Annotated[RepositoryRepository, Depends(get_repository_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
    sandbox: Annotated[SandboxUserWorkspaceClient, Depends(get_sandbox_workspace_gateway)],
) -> EnsureUserRepositoryWorkspace:
    return EnsureUserRepositoryWorkspace(workspaces, repos, access, sandbox)


def get_list_user_workspaces_uc(
    workspaces: Annotated[UserRepositoryWorkspaceRepository, Depends(get_user_workspace_repo)],
) -> ListUserRepositoryWorkspaces:
    return ListUserRepositoryWorkspaces(workspaces)


def get_delete_user_workspace_uc(
    workspaces: Annotated[UserRepositoryWorkspaceRepository, Depends(get_user_workspace_repo)],
    sandbox: Annotated[SandboxUserWorkspaceClient, Depends(get_sandbox_workspace_gateway)],
) -> DeleteUserRepositoryWorkspace:
    return DeleteUserRepositoryWorkspace(workspaces, sandbox)


def get_list_ai_models_uc(
    catalog: Annotated[ModelCatalogService, Depends(get_model_catalog_service)],
) -> ListAiModels:
    return ListAiModels(catalog)


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
    user_workspaces: Annotated[
        EnsureUserRepositoryWorkspace,
        Depends(get_ensure_user_workspace_uc),
    ],
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
        user_workspaces=user_workspaces,
    )


def get_list_chat_commands_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
    runtime: Annotated[ChatCommandRuntimePort, Depends(get_chat_command_runtime)],
    model_profiles: Annotated[ModelProfileLookupPort, Depends(get_model_profile_lookup)],
    sandboxes: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> ListChatCommands:
    return ListChatCommands(convs, runtime, model_profiles, sandboxes=sandboxes)


def get_execute_chat_command_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
    msgs: Annotated[MessageRepository, Depends(get_msg_repo)],
    runtime: Annotated[ChatCommandRuntimePort, Depends(get_chat_command_runtime)],
    catalog: Annotated[ListChatCommands, Depends(get_list_chat_commands_uc)],
) -> ExecuteChatCommand:
    return ExecuteChatCommand(convs, msgs, runtime, catalog)


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
