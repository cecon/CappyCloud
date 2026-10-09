"""Contrato de ``WorkspaceReportRepository``: fake em memória e SQLAlchemy (SQLite)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from app.adapters.secondary.persistence.sqlalchemy_workspace_report_repo import (
    SQLAlchemyWorkspaceReportRepository,
)
from app.infrastructure.orm_models import Base, Conversation, Message, Sandbox
from app.infrastructure.orm_models import User as UserORM
from app.infrastructure.orm_models_workspaces import UserWorkspaceAccess, Workspace
from app.ports.workspace_report import (
    ReportConversation,
    ReportMessage,
    ReportWorkspace,
    WorkspaceReportRepository,
    branches_from_repos,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.fakes_reports import InMemoryWorkspaceReportRepository

T0 = datetime(2026, 9, 1, 12, tzinfo=UTC)


@dataclass
class Seed:
    repo: WorkspaceReportRepository
    proteus: uuid.UUID
    seller: uuid.UUID
    analyst: uuid.UUID
    conv_main: uuid.UUID
    conv_master: uuid.UUID


# (conversa, workspace, título, repos, mensagens[(papel, conteúdo, minutos depois de T0, custo)])
def _plan(ids: dict[str, uuid.UUID]) -> list[tuple[uuid.UUID, uuid.UUID, str, list, list]]:
    return [
        (
            ids["conv_main"],
            ids["proteus"],
            "Rejeição E160",
            [{"base_branch": "main", "branch_name": None}],
            [
                ("assistant", "resposta antes", -1, 9.0),
                ("user", "primeira pergunta", 0, 0.0),
                ("assistant", "resposta", 5, 1.25),
                ("user", "segunda pergunta", 10, 0.0),
                ("assistant", "fim", 60, 2.0),
            ],
        ),
        (
            ids["conv_master"],
            ids["seller"],
            "SAP",
            [{"base_branch": "master", "branch_name": "cappy/x"}],
            [("user", "como ativar o sap", 30, 0.0)],
        ),
    ]


async def _seed_fake(ids: dict[str, uuid.UUID]) -> InMemoryWorkspaceReportRepository:
    repo = InMemoryWorkspaceReportRepository()
    repo.add_workspace(ReportWorkspace(ids["proteus"], "proteus", "PROTEUS", "nfse-protheus"))
    repo.add_workspace(ReportWorkspace(ids["seller"], "seller", "SELLER"))
    repo.grant(ids["analyst"], ids["seller"])
    for conv_id, ws_id, title, repos, msgs in _plan(ids):
        first = next(content for role, content, *_ in msgs if role == "user")
        repo.add_conversation(
            ReportConversation(
                conv_id, ws_id, "ana@linx.com", title, None, branches_from_repos(repos), first
            ),
            *(
                ReportMessage(conv_id, T0 + timedelta(minutes=m), cost)
                for _role, _content, m, cost in msgs
            ),
        )
    return repo


async def _seed_sql(ids: dict[str, uuid.UUID]) -> AsyncGenerator[WorkspaceReportRepository]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        sandbox = Sandbox(id=uuid.uuid4(), name="sb", host="sb", session_port=8080)
        session.add_all(
            [sandbox, UserORM(id=ids["analyst"], email="ana@linx.com", hashed_password="x")]
        )
        await session.flush()
        session.add_all(
            [
                Workspace(
                    id=ids["proteus"],
                    slug="proteus",
                    name="PROTEUS",
                    sandbox_id=sandbox.id,
                    report_theme_preset="nfse-protheus",
                ),
                Workspace(id=ids["seller"], slug="seller", name="SELLER", sandbox_id=sandbox.id),
                # Conversa sem workspace nunca entra.
                Conversation(id=uuid.uuid4(), user_id=ids["analyst"], title="solta"),
            ]
        )
        await session.flush()
        session.add(
            UserWorkspaceAccess(id=uuid.uuid4(), user_id=ids["analyst"], workspace_id=ids["seller"])
        )
        for conv_id, ws_id, title, repos, msgs in _plan(ids):
            session.add(
                Conversation(
                    id=conv_id, user_id=ids["analyst"], workspace_id=ws_id, title=title, repos=repos
                )
            )
            await session.flush()
            for role, content, minutes, cost in msgs:
                session.add(
                    Message(
                        id=uuid.uuid4(),
                        conversation_id=conv_id,
                        role=role,
                        content=content,
                        cost_usd=cost,
                        created_at=T0 + timedelta(minutes=minutes),
                    )
                )
        await session.commit()
        yield SQLAlchemyWorkspaceReportRepository(session)
    await engine.dispose()


@pytest_asyncio.fixture(params=["fake", "sqlalchemy"])
async def seed(request: pytest.FixtureRequest) -> AsyncGenerator[Seed]:
    ids = {k: uuid.uuid4() for k in ("proteus", "seller", "analyst", "conv_main", "conv_master")}
    if request.param == "fake":
        yield Seed(repo=await _seed_fake(ids), **ids)
        return
    async for repo in _seed_sql(ids):
        yield Seed(repo=repo, **ids)


async def test_list_workspaces_sorted_by_name_with_theme_config(seed: Seed) -> None:
    workspaces = await seed.repo.list_workspaces()
    assert [(w.slug, w.theme_preset, w.theme_rules) for w in workspaces] == [
        ("proteus", "nfse-protheus", None),
        ("seller", None, None),
    ]


async def test_accessible_workspace_ids(seed: Seed) -> None:
    assert await seed.repo.accessible_workspace_ids(seed.analyst) == {seed.seller}
    assert await seed.repo.accessible_workspace_ids(uuid.uuid4()) == set()


async def test_period_messages_start_inclusive_end_exclusive(seed: Seed) -> None:
    msgs = await seed.repo.list_period_messages([seed.proteus], T0, T0 + timedelta(minutes=60))
    assert sorted((m.created_at, m.cost_usd) for m in msgs) == [
        (T0, 0.0),
        (T0 + timedelta(minutes=5), 1.25),
        (T0 + timedelta(minutes=10), 0.0),
    ]
    assert all(m.conversation_id == seed.conv_main for m in msgs)
    assert await seed.repo.list_period_messages([], T0, T0 + timedelta(days=1)) == []


async def test_get_conversations_brings_email_branches_and_first_user_message(seed: Seed) -> None:
    convs = {c.id: c for c in await seed.repo.get_conversations([seed.conv_main, seed.conv_master])}
    main = convs[seed.conv_main]
    assert (main.workspace_id, main.user_email, main.title) == (
        seed.proteus,
        "ana@linx.com",
        "Rejeição E160",
    )
    assert main.first_user_message == "primeira pergunta"
    assert main.branches == {"main"}
    assert convs[seed.conv_master].branches == {"master", "cappy/x"}
    assert await seed.repo.get_conversations([]) == []


async def test_list_branches_per_scope(seed: Seed) -> None:
    assert await seed.repo.list_branches([seed.proteus]) == ["main"]
    assert await seed.repo.list_branches([seed.proteus, seed.seller]) == [
        "cappy/x",
        "main",
        "master",
    ]
    assert await seed.repo.list_branches([]) == []


async def test_save_theme_config(seed: Seed) -> None:
    rules = [{"key": "a", "label": "A", "patterns": ["x"]}]
    saved = await seed.repo.save_theme_config(seed.seller, "generico", rules)
    assert saved is not None
    assert (saved.theme_preset, saved.theme_rules) == ("generico", rules)
    cleared = await seed.repo.save_theme_config(seed.seller, None, None)
    assert cleared is not None
    assert (cleared.theme_preset, cleared.theme_rules) == (None, None)
    assert await seed.repo.save_theme_config(uuid.uuid4(), None, None) is None
