"""Use cases for creating, preparing, and running agentic delivery cycles."""

from __future__ import annotations

import uuid

from app.domain.agentic_delivery import (
    CycleStatus,
    EvidenceSourceType,
    surface_matches,
    validate_transition,
)
from app.domain.entities import UserRole
from app.ports.agent import AgentPort
from app.ports.agentic_delivery import AgenticDeliveryRepository, CycleCreate
from app.ports.repositories import RepositoryRepository
from app.ports.user_access import AiModelAccessPolicy, UserRepositoryAccessRepository


class CreateAgenticDeliveryCycle:
    def __init__(
        self,
        repo: AgenticDeliveryRepository,
        access: UserRepositoryAccessRepository,
    ) -> None:
        self._repo = repo
        self._access = access

    async def execute(
        self,
        user_id: uuid.UUID,
        user_role: UserRole,
        payload: dict,
    ) -> dict:
        await self._ensure_repository_access(user_id, user_role, payload["repository_ids"])
        cycle = await self._repo.create_cycle(
            CycleCreate(
                created_by_user_id=user_id,
                conversation_id=payload.get("conversation_id"),
                repository_ids=payload["repository_ids"],
                domain_key=payload.get("domain_key"),
                title=payload["title"].strip(),
                business_goal=payload["business_goal"].strip(),
                scope_boundary=payload["scope_boundary"].strip(),
                expected_outputs=payload["expected_outputs"],
                acceptance_expectations=payload["acceptance_expectations"],
            )
        )
        await self._repo.add_evidence_sources(
            cycle["id"],
            [self._evidence_source(item) for item in payload.get("evidence_sources", [])],
        )
        return cycle

    async def _ensure_repository_access(
        self, user_id: uuid.UUID, user_role: UserRole, repository_ids: list[uuid.UUID]
    ) -> None:
        if user_role is UserRole.ADMIN:
            return
        for repo_id in repository_ids:
            if not await self._access.has_access(user_id, repo_id):
                raise PermissionError("Usuário sem acesso ao repositório selecionado.")

    @staticmethod
    def _evidence_source(item: dict) -> dict:
        return {
            "source_type": EvidenceSourceType(item["source_type"]).value,
            "repository_id": item.get("repository_id"),
            "document_id": item.get("document_id"),
            "attachment_id": item.get("attachment_id"),
            "source_url": item.get("source_url"),
            "title": item["title"],
            "scope_note": item.get("scope_note", ""),
            "available": True,
        }


class PrepareStructuredWorkPackage:
    def __init__(
        self,
        repo: AgenticDeliveryRepository,
        access: UserRepositoryAccessRepository,
    ) -> None:
        self._repo = repo
        self._access = access

    async def execute(self, cycle_id: uuid.UUID, user_id: uuid.UUID, user_role: UserRole) -> dict:
        cycle = await self._require_cycle(cycle_id)
        await self._ensure_cycle_access(cycle, user_id, user_role)
        missing = self._missing_inputs(cycle)
        if missing:
            return {"cycle": cycle, "work_package": None, "missing_inputs": missing}
        work_package = await self._repo.create_work_package(
            cycle_id,
            instructions=self._instructions(cycle),
            constraints=[cycle["scope_boundary"]],
            review_criteria=cycle["acceptance_expectations"],
            source_summary={"repository_ids": [str(r) for r in cycle["repository_ids"]]},
        )
        await self._apply_sensitive_surface_triggers(cycle, work_package)
        if cycle["status"] == CycleStatus.DRAFT.value:
            await self._repo.update_cycle_status(
                cycle_id,
                CycleStatus.DRAFT,
                CycleStatus.READY,
                None,
                "Pacote estruturado preparado.",
            )
            cycle = await self._require_cycle(cycle_id)
        return {
            "cycle": cycle,
            "work_package": work_package,
            "missing_inputs": [],
            "required_gates": [
                gate["gate_type"]
                for gate in await self._repo.list_gates(cycle_id)
                if gate.get("required")
            ],
        }

    async def _require_cycle(self, cycle_id: uuid.UUID) -> dict:
        cycle = await self._repo.get_cycle(cycle_id)
        if not cycle:
            raise LookupError("Ciclo não encontrado.")
        return cycle

    async def _ensure_cycle_access(
        self, cycle: dict, user_id: uuid.UUID, user_role: UserRole
    ) -> None:
        if user_role is UserRole.ADMIN:
            return
        for repo_id in cycle["repository_ids"]:
            if not await self._access.has_access(user_id, repo_id):
                raise PermissionError("Usuário sem acesso ao ciclo selecionado.")

    @staticmethod
    def _missing_inputs(cycle: dict) -> list[str]:
        missing: list[str] = []
        for key in ("business_goal", "scope_boundary", "title"):
            if not str(cycle.get(key) or "").strip():
                missing.append(key)
        for key in ("repository_ids", "expected_outputs", "acceptance_expectations"):
            if not cycle.get(key):
                missing.append(key)
        return missing

    @staticmethod
    def _instructions(cycle: dict) -> str:
        outputs = ", ".join(cycle["expected_outputs"])
        return (
            f"Objetivo: {cycle['business_goal']}\n"
            f"Escopo: {cycle['scope_boundary']}\n"
            f"Saídas: {outputs}"
        )

    async def _apply_sensitive_surface_triggers(self, cycle: dict, work_package: dict) -> None:
        texts = [
            cycle["title"],
            cycle["business_goal"],
            cycle["scope_boundary"],
            work_package["instructions"],
            *cycle["expected_outputs"],
            *cycle["acceptance_expectations"],
        ]
        paths = [
            str(source.get("source_url") or source.get("title") or "")
            for source in work_package.get("source_summary", {}).get("evidence_sources", [])
        ]
        for repo_id in cycle["repository_ids"]:
            surfaces = await self._repo.list_sensitive_surfaces(
                repo_id,
                cycle.get("domain_key"),
                limit=100,
                cursor=None,
            )
            for surface in surfaces.items:
                if surface_matches(surface["match_rules"], texts, paths):
                    await self._repo.ensure_compliance_gate(
                        cycle["id"],
                        f"Superfície sensível detectada: {surface['name']}",
                    )
                    return


class RunAgenticDeliveryCycle:
    def __init__(
        self,
        repo: AgenticDeliveryRepository,
        agent: AgentPort,
        model_access: AiModelAccessPolicy,
        access: UserRepositoryAccessRepository,
        repositories: RepositoryRepository | None = None,
    ) -> None:
        self._repo = repo
        self._agent = agent
        self._model_access = model_access
        self._access = access
        self._repositories = repositories

    async def execute(
        self,
        cycle_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: UserRole,
        model_id: str | None,
        execution_window: str | None,
    ) -> dict:
        cycle = await self._require_cycle(cycle_id)
        await self._ensure_cycle_access(cycle, user_id, user_role)
        if cycle["status"] != CycleStatus.READY.value:
            raise RuntimeError("O ciclo precisa estar Ready para iniciar execução.")
        work_package = await self._repo.latest_work_package(cycle_id)
        if not work_package:
            raise RuntimeError("Pacote de trabalho obrigatório não encontrado.")
        effective_model = await self._model_access.resolve_model_for_user(
            user_id, user_role, model_id
        )
        task_id = await self._agent.dispatch(
            prompt=self._agentic_prompt(cycle, work_package),
            conversation_id=str(cycle["conversation_id"]) if cycle.get("conversation_id") else None,
            triggered_by="agentic_delivery",
            trigger_payload=self._cycle_context(
                cycle, work_package, effective_model, execution_window
            ),
            repos=await self._repo_payload(cycle),
            sandbox_id=await self._sandbox_id(cycle),
            override_model=effective_model,
        )
        validate_transition(CycleStatus.READY, CycleStatus.RUNNING)
        cycle = await self._repo.update_cycle_status(
            cycle_id,
            CycleStatus.READY,
            CycleStatus.RUNNING,
            user_id,
            "Execução do agente iniciada.",
        )
        return {"cycle": cycle, "agent_task_id": uuid.UUID(task_id) if task_id else None}

    def _cycle_context(
        self,
        cycle: dict,
        work_package: dict,
        model_id: str | None,
        execution_window: str | None,
    ) -> dict:
        return {
            "cycle_id": str(cycle["id"]),
            "domain_key": cycle.get("domain_key"),
            "repository_ids": [str(r) for r in cycle["repository_ids"]],
            "work_package_id": str(work_package["id"]),
            "work_package_version": work_package["version"],
            "execution_window": execution_window,
            "review_only": True,
            "model_id": model_id,
        }

    @staticmethod
    def _agentic_prompt(cycle: dict, work_package: dict) -> str:
        criteria = "\n".join(f"- {item}" for item in work_package["review_criteria"])
        constraints = "\n".join(f"- {item}" for item in work_package["constraints"])
        return (
            "## Ciclo Agentic Delivery\n\n"
            f"ID: `{cycle['id']}`\n"
            f"Título: {cycle['title']}\n"
            f"Domínio: {cycle.get('domain_key') or 'não informado'}\n\n"
            "## Pacote de Trabalho\n\n"
            f"{work_package['instructions']}\n\n"
            "## Restrições\n\n"
            f"{constraints}\n\n"
            "## Critérios de revisão esperados\n\n"
            f"{criteria}\n\n"
            "Mantenha qualquer alteração em contexto de revisão. Não faça push, deploy, "
            "merge, alteração irreversível ou ação externa; produza evidências e indique "
            "explicitamente qualquer afirmação sem suporte."
        )

    async def _repo_payload(self, cycle: dict) -> list[dict]:
        if self._repositories is None:
            return [{"repo_id": str(repo_id)} for repo_id in cycle["repository_ids"]]
        repos: list[dict] = []
        for repo_id in cycle["repository_ids"]:
            repo = await self._repositories.get(repo_id)
            if repo is None:
                continue
            clone_url = await self._repositories.get_authenticated_clone_url(repo_id)
            repos.append(
                {
                    "repo_id": str(repo.id),
                    "slug": repo.slug,
                    "alias": repo.slug,
                    "clone_url": clone_url or repo.clone_url,
                    "default_branch": repo.default_branch,
                    "sandbox_id": str(repo.sandbox_id) if repo.sandbox_id else "",
                }
            )
        return repos

    async def _sandbox_id(self, cycle: dict) -> str:
        if self._repositories is None:
            return ""
        for repo_id in cycle["repository_ids"]:
            repo = await self._repositories.get(repo_id)
            if repo and repo.sandbox_id:
                return str(repo.sandbox_id)
        return ""

    async def _require_cycle(self, cycle_id: uuid.UUID) -> dict:
        cycle = await self._repo.get_cycle(cycle_id)
        if not cycle:
            raise LookupError("Ciclo não encontrado.")
        return cycle

    async def _ensure_cycle_access(
        self, cycle: dict, user_id: uuid.UUID, user_role: UserRole
    ) -> None:
        if user_role is UserRole.ADMIN:
            return
        for repo_id in cycle["repository_ids"]:
            if not await self._access.has_access(user_id, repo_id):
                raise PermissionError("Usuário sem acesso ao ciclo selecionado.")
