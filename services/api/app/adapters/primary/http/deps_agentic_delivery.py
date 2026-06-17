"""FastAPI dependencies for agentic delivery HTTP adapters."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import (
    get_agent,
    get_ai_model_access_policy,
    get_db_session,
    get_repository_repo,
    get_user_repository_access_repo,
)
from app.adapters.secondary.persistence.sqlalchemy_agentic_delivery_repo import (
    SQLAlchemyAgenticDeliveryRepository,
)
from app.application.use_cases.agentic_delivery_actions import AuthorizeExternalAction
from app.application.use_cases.agentic_delivery_knowledge import SearchReusableKnowledge
from app.application.use_cases.agentic_delivery_metrics import GetCycleMetrics
from app.application.use_cases.agentic_delivery_prepare import (
    CreateAgenticDeliveryCycle,
    PrepareStructuredWorkPackage,
    RunAgenticDeliveryCycle,
)
from app.application.use_cases.agentic_delivery_review import (
    GetReviewPackage,
    LinkAgentOutputEvidence,
    ManageAgenticDeliveryPermissions,
    ManageSensitiveSurfaces,
    RecordReviewDecision,
    TransitionAgenticDeliveryCycle,
)
from app.ports.agent import AgentPort
from app.ports.agentic_delivery import AgenticDeliveryRepository
from app.ports.repositories import RepositoryRepository
from app.ports.user_access import AiModelAccessPolicy, UserRepositoryAccessRepository


def get_agentic_delivery_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgenticDeliveryRepository:
    return SQLAlchemyAgenticDeliveryRepository(session)


def get_create_agentic_cycle_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
) -> CreateAgenticDeliveryCycle:
    return CreateAgenticDeliveryCycle(repo, access)


def get_prepare_agentic_cycle_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
) -> PrepareStructuredWorkPackage:
    return PrepareStructuredWorkPackage(repo, access)


def get_run_agentic_cycle_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
    agent: Annotated[AgentPort, Depends(get_agent)],
    model_access: Annotated[AiModelAccessPolicy, Depends(get_ai_model_access_policy)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
    repositories: Annotated[RepositoryRepository, Depends(get_repository_repo)],
) -> RunAgenticDeliveryCycle:
    return RunAgenticDeliveryCycle(repo, agent, model_access, access, repositories)


def get_review_package_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
) -> GetReviewPackage:
    return GetReviewPackage(repo, access)


def get_record_review_decision_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
) -> RecordReviewDecision:
    return RecordReviewDecision(repo, access)


def get_link_agentic_output_evidence_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
) -> LinkAgentOutputEvidence:
    return LinkAgentOutputEvidence(repo, access)


def get_transition_agentic_cycle_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
) -> TransitionAgenticDeliveryCycle:
    return TransitionAgenticDeliveryCycle(repo, access)


def get_search_agentic_knowledge_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
) -> SearchReusableKnowledge:
    return SearchReusableKnowledge(repo, access)


def get_manage_sensitive_surfaces_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
) -> ManageSensitiveSurfaces:
    return ManageSensitiveSurfaces(repo)


def get_manage_agentic_permissions_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
) -> ManageAgenticDeliveryPermissions:
    return ManageAgenticDeliveryPermissions(repo)


def get_authorize_external_action_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
) -> AuthorizeExternalAction:
    return AuthorizeExternalAction(repo)


def get_cycle_metrics_uc(
    repo: Annotated[AgenticDeliveryRepository, Depends(get_agentic_delivery_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
) -> GetCycleMetrics:
    return GetCycleMetrics(repo, access)
