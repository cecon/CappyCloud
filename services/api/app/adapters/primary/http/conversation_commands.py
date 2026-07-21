"""HTTP adapter for chat slash commands."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import (
    get_authenticated_user,
    get_conv_repo,
    get_db_session,
    get_msg_repo,
    get_sandbox_repo,
)
from app.adapters.secondary.persistence.sqlalchemy_model_profiles import (
    SQLAlchemyModelProfileLookup,
)
from app.adapters.secondary.sandbox_runtime.chat_commands import SandboxChatCommandRuntime
from app.application.use_cases.chat_command_execution import ExecuteChatCommand
from app.application.use_cases.chat_commands import ListChatCommands
from app.domain.chat_commands import CommandExecutionStatus
from app.domain.entities import User
from app.ports.chat_commands import ChatCommandRuntimePort
from app.ports.model_profiles import ModelProfileLookupPort
from app.ports.repositories import ConversationRepository, MessageRepository, SandboxRepository
from app.schemas_chat_commands import (
    CommandArgumentOut,
    CommandAvailabilityOut,
    CommandCatalogOut,
    CommandConfirmationOut,
    CommandExecuteIn,
    CommandExecuteOut,
    CommandStreamOut,
    SlashCommandOut,
)

router = APIRouter(prefix="/conversations", tags=["conversation-commands"])


def get_model_profile_lookup(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ModelProfileLookupPort:
    return SQLAlchemyModelProfileLookup(session)


def get_chat_command_runtime() -> ChatCommandRuntimePort:
    return SandboxChatCommandRuntime()


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


@router.get("/{conversation_id}/commands", response_model=CommandCatalogOut)
async def list_conversation_commands(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ListChatCommands, Depends(get_list_chat_commands_uc)],
) -> CommandCatalogOut:
    try:
        catalog = await uc.execute(conversation_id, current)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CommandCatalogOut(
        runtime_version=catalog.runtime_version,
        runtime_commit=catalog.runtime_commit,
        generated_at=catalog.generated_at,
        commands=[
            SlashCommandOut(
                name=command.name,
                description=command.description,
                source=command.source.value,
                category=command.category.value,
                arguments=[
                    CommandArgumentOut(
                        name=arg.name,
                        label=arg.label,
                        required=arg.required,
                        value_hint=arg.value_hint,
                        allowed_values=arg.allowed_values,
                        sensitive=arg.sensitive,
                    )
                    for arg in command.arguments
                ],
                availability=CommandAvailabilityOut(
                    state=command.availability.state.value,
                    reason=command.availability.reason,
                    required_role=command.availability.required_role,
                    required_capability=command.availability.required_capability,
                ),
                requires_confirmation=command.requires_confirmation,
                confirmation_reason=command.confirmation_reason,
                execution_mode=command.execution_mode.value,
            )
            for command in catalog.commands
        ],
    )


@router.post("/{conversation_id}/commands/execute", response_model=CommandExecuteOut)
async def execute_conversation_command(
    conversation_id: uuid.UUID,
    body: CommandExecuteIn,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ExecuteChatCommand, Depends(get_execute_chat_command_uc)],
) -> CommandExecuteOut:
    try:
        decision = await uc.execute(
            conversation_id=conversation_id,
            user=current,
            command_name=body.command,
            arguments=body.arguments,
            confirmed=body.confirmed,
            client_request_id=body.client_request_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if decision.status is CommandExecutionStatus.NEEDS_CONFIRMATION:
        return CommandExecuteOut(
            status="needs_confirmation",
            message=decision.message,
            confirmation=CommandConfirmationOut(**(decision.confirmation or {})),
        )
    if decision.status is CommandExecutionStatus.UNAVAILABLE:
        return CommandExecuteOut(status="unavailable", message=decision.message)
    if decision.status is CommandExecutionStatus.FAILED:
        return CommandExecuteOut(status="failed", message=decision.message)
    if decision.status is CommandExecutionStatus.CANCELLED:
        return CommandExecuteOut(status="cancelled", message=decision.message)
    if decision.status is CommandExecutionStatus.WAITING_FOR_INPUT:
        return CommandExecuteOut(status="waiting_for_input", message=decision.message)
    if decision.status is CommandExecutionStatus.STARTED:
        return CommandExecuteOut(
            status="started",
            message=decision.message,
            stream=CommandStreamOut(
                conversation_id=str(conversation_id),
                client_request_id=body.client_request_id,
            ),
        )
    return CommandExecuteOut(
        status="completed" if decision.status is CommandExecutionStatus.COMPLETED else "accepted",
        message=decision.message,
        stream=CommandStreamOut(
            conversation_id=str(conversation_id),
            client_request_id=body.client_request_id,
        ),
    )
