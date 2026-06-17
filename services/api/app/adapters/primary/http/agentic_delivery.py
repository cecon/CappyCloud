"""HTTP adapter for agentic delivery cycles."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.adapters.primary.http.deps import get_authenticated_user
from app.adapters.primary.http.deps_agentic_delivery import (
    get_authorize_external_action_uc,
    get_create_agentic_cycle_uc,
    get_cycle_metrics_uc,
    get_link_agentic_output_evidence_uc,
    get_prepare_agentic_cycle_uc,
    get_record_review_decision_uc,
    get_review_package_uc,
    get_run_agentic_cycle_uc,
    get_search_agentic_knowledge_uc,
    get_transition_agentic_cycle_uc,
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
    RecordReviewDecision,
    TransitionAgenticDeliveryCycle,
)
from app.domain.agentic_delivery import (
    CycleStatus,
    DeniedExternalActionError,
    EvidenceSupportStatus,
    IncompleteGatesError,
    InvalidTransitionError,
    ReviewDecisionValue,
)
from app.domain.entities import User
from app.schemas_agentic_delivery import (
    CreateCycleRequest,
    CycleCreatedResponse,
    EvidenceLinkOut,
    EvidenceLinkRequest,
    ExternalActionAuthorizationRequest,
    ExternalActionAuthorizationResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    MetricsResponse,
    PrepareWorkPackageResponse,
    RecordReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewPackageResponse,
    RunCycleRequest,
    RunCycleResponse,
    TransitionCycleRequest,
    TransitionCycleResponse,
)

router = APIRouter(prefix="/agentic-cycles", tags=["agentic-delivery"])


@router.post("", response_model=CycleCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_cycle(
    body: CreateCycleRequest,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[CreateAgenticDeliveryCycle, Depends(get_create_agentic_cycle_uc)],
) -> CycleCreatedResponse:
    try:
        cycle = await uc.execute(current.id, current.role, body.model_dump())
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return CycleCreatedResponse(
        id=cycle["id"],
        status=cycle["status"],
        required_gates=["product", "architecture", "quality"],
        created_at=cycle["created_at"],
    )


@router.post("/{cycle_id}/prepare", response_model=PrepareWorkPackageResponse)
async def prepare_cycle(
    cycle_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[PrepareStructuredWorkPackage, Depends(get_prepare_agentic_cycle_uc)],
) -> PrepareWorkPackageResponse:
    try:
        result = await uc.execute(cycle_id, current.id, current.role)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    work_package = result["work_package"]
    cycle = result["cycle"]
    return PrepareWorkPackageResponse(
        cycle_id=cycle_id,
        status=cycle["status"],
        work_package_id=work_package["id"] if work_package else uuid.UUID(int=0),
        missing_inputs=result["missing_inputs"],
        required_gates=result.get("required_gates", ["product", "architecture", "quality"]),
    )


@router.post("/{cycle_id}/run", response_model=RunCycleResponse, status_code=202)
async def run_cycle(
    cycle_id: uuid.UUID,
    body: RunCycleRequest,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[RunAgenticDeliveryCycle, Depends(get_run_agentic_cycle_uc)],
) -> RunCycleResponse:
    try:
        result = await uc.execute(
            cycle_id, current.id, current.role, body.model_id, body.execution_window
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RunCycleResponse(
        cycle_id=cycle_id,
        status=result["cycle"]["status"],
        agent_task_id=result["agent_task_id"],
    )


@router.get("/{cycle_id}/review", response_model=ReviewPackageResponse)
async def get_review(
    cycle_id: uuid.UUID,
    uc: Annotated[GetReviewPackage, Depends(get_review_package_uc)],
    current: Annotated[User, Depends(get_authenticated_user)],
    outputs_limit: int = Query(default=50, ge=1, le=100),
    outputs_cursor: str | None = Query(default=None),
    decisions_limit: int = Query(default=20, ge=1, le=100),
    decisions_cursor: str | None = Query(default=None),
) -> ReviewPackageResponse:
    try:
        result = await uc.execute(
            cycle_id,
            current.id,
            current.role,
            outputs_limit,
            outputs_cursor,
            decisions_limit,
            decisions_cursor,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ReviewPackageResponse(**result)


@router.post("/{cycle_id}/review-decisions", response_model=ReviewDecisionResponse, status_code=201)
async def record_decision(
    cycle_id: uuid.UUID,
    body: RecordReviewDecisionRequest,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[RecordReviewDecision, Depends(get_record_review_decision_uc)],
) -> ReviewDecisionResponse:
    try:
        result = await uc.execute(
            cycle_id,
            current.id,
            current.role,
            ReviewDecisionValue(body.decision),
            body.rationale,
            body.agent_output_id,
            body.review_gate_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    decision = result["decision"]
    return ReviewDecisionResponse(
        id=decision["id"],
        cycle_id=cycle_id,
        decision=decision["decision"],
        cycle_status=result["cycle"]["status"],
    )


@router.post(
    "/{cycle_id}/outputs/{output_id}/evidence-links",
    response_model=EvidenceLinkOut,
    status_code=status.HTTP_201_CREATED,
)
async def link_output_evidence(
    cycle_id: uuid.UUID,
    output_id: uuid.UUID,
    body: EvidenceLinkRequest,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[LinkAgentOutputEvidence, Depends(get_link_agentic_output_evidence_uc)],
) -> EvidenceLinkOut:
    try:
        row = await uc.execute(
            cycle_id,
            current.id,
            current.role,
            output_id,
            body.evidence_source_id,
            body.claim_summary,
            EvidenceSupportStatus(body.support_status),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return EvidenceLinkOut(**row)


@router.post("/{cycle_id}/transition", response_model=TransitionCycleResponse)
async def transition_cycle(
    cycle_id: uuid.UUID,
    body: TransitionCycleRequest,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[TransitionAgenticDeliveryCycle, Depends(get_transition_agentic_cycle_uc)],
) -> TransitionCycleResponse:
    try:
        result = await uc.execute(
            cycle_id, current.id, current.role, CycleStatus(body.to_status), body.reason
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (InvalidTransitionError, IncompleteGatesError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return TransitionCycleResponse(
        cycle_id=cycle_id,
        from_status=result["from_status"],
        to_status=result["cycle"]["status"],
    )


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    body: KnowledgeSearchRequest,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[SearchReusableKnowledge, Depends(get_search_agentic_knowledge_uc)],
) -> KnowledgeSearchResponse:
    result = await uc.execute(
        current.id,
        current.role,
        body.repository_ids,
        body.domain_key,
        body.query,
        body.limit,
        body.cursor,
    )
    return KnowledgeSearchResponse(**result)


@router.post(
    "/{cycle_id}/external-actions/authorize",
    response_model=ExternalActionAuthorizationResponse,
    status_code=201,
)
async def authorize_external_action(
    cycle_id: uuid.UUID,
    body: ExternalActionAuthorizationRequest,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[AuthorizeExternalAction, Depends(get_authorize_external_action_uc)],
) -> ExternalActionAuthorizationResponse:
    try:
        row = await uc.execute(cycle_id, current.id, body.model_dump())
    except DeniedExternalActionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ExternalActionAuthorizationResponse(**row)


@router.get("/{cycle_id}/metrics", response_model=MetricsResponse)
async def get_metrics(
    cycle_id: uuid.UUID,
    uc: Annotated[GetCycleMetrics, Depends(get_cycle_metrics_uc)],
    current: Annotated[User, Depends(get_authenticated_user)],
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> MetricsResponse:
    try:
        result = await uc.execute(cycle_id, current.id, current.role, limit, cursor)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return MetricsResponse(**result)
