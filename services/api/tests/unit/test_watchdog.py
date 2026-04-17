"""Unit tests for SandboxWatchdog — uses mocks, no real DB or HTTP."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.infrastructure.sandbox_watchdog import SandboxWatchdog


def _make_item(
    operation: str = "clone_repo",
    status: str = "pending",
    retries: int = 0,
    sandbox_id: uuid.UUID | None = None,
) -> MagicMock:
    item = MagicMock()
    item.sandbox_id = sandbox_id or uuid.uuid4()
    item.operation = operation
    item.status = status
    item.retries = retries
    item.last_error = None
    item.payload = {"slug": "myrepo", "clone_url": "https://github.com/x/y"}
    return item


def _make_sandbox(host: str = "sandbox-host", port: int = 8080) -> MagicMock:
    sb = MagicMock()
    sb.host = host
    sb.session_port = port
    return sb


@pytest.fixture
def session() -> AsyncMock:
    s = AsyncMock()
    s.execute = AsyncMock()
    s.get = AsyncMock()
    s.flush = AsyncMock()
    s.commit = AsyncMock()
    return s


@pytest.fixture
def watchdog() -> SandboxWatchdog:
    factory = MagicMock()
    return SandboxWatchdog(factory)


class TestProcessPending:
    async def test_no_items_returns_early(
        self, watchdog: SandboxWatchdog, session: AsyncMock
    ) -> None:
        rows = MagicMock()
        rows.scalars.return_value = iter([])
        session.execute.return_value = rows

        await watchdog._process_pending(session)

        session.flush.assert_not_called()
        session.commit.assert_not_called()

    async def test_sandbox_not_found_marks_error(
        self, watchdog: SandboxWatchdog, session: AsyncMock
    ) -> None:
        item = _make_item()
        rows = MagicMock()
        rows.scalars.return_value = iter([item])
        session.execute.return_value = rows
        session.get.return_value = None  # sandbox not found

        await watchdog._process_pending(session)

        assert item.status == "error"
        assert "sandbox not found" in item.last_error
        session.commit.assert_called_once()

    async def test_successful_operation_marks_done(
        self, watchdog: SandboxWatchdog, session: AsyncMock
    ) -> None:
        item = _make_item(operation="clone_repo")
        sandbox = _make_sandbox()
        rows = MagicMock()
        rows.scalars.return_value = iter([item])
        session.execute.return_value = rows
        session.get.return_value = sandbox

        with patch.object(watchdog, "_execute", new=AsyncMock()) as mock_exec:
            await watchdog._process_pending(session)

        mock_exec.assert_called_once_with(sandbox, "clone_repo", item.payload)
        assert item.status == "done"
        assert item.last_error is None

    async def test_failed_operation_increments_retries(
        self, watchdog: SandboxWatchdog, session: AsyncMock
    ) -> None:
        item = _make_item(operation="clone_repo", retries=0)
        sandbox = _make_sandbox()
        rows = MagicMock()
        rows.scalars.return_value = iter([item])
        session.execute.return_value = rows
        session.get.return_value = sandbox

        with patch.object(watchdog, "_execute", new=AsyncMock(side_effect=RuntimeError("boom"))):
            await watchdog._process_pending(session)

        assert item.retries == 1
        assert item.status == "pending"
        assert "boom" in item.last_error

    async def test_max_retries_marks_error(
        self, watchdog: SandboxWatchdog, session: AsyncMock
    ) -> None:
        item = _make_item(retries=2)  # retries == _MAX_RETRIES - 1, becomes 3 → error
        sandbox = _make_sandbox()
        rows = MagicMock()
        rows.scalars.return_value = iter([item])
        session.execute.return_value = rows
        session.get.return_value = sandbox

        with patch.object(watchdog, "_execute", new=AsyncMock(side_effect=RuntimeError("fail"))):
            await watchdog._process_pending(session)

        assert item.status == "error"


class TestExecute:
    async def test_unknown_operation_raises(self, watchdog: SandboxWatchdog) -> None:
        sandbox = _make_sandbox()
        with pytest.raises(ValueError, match="operação desconhecida"):
            await watchdog._execute(sandbox, "do_nothing", {})

    async def test_reconfigure_model_is_noop(self, watchdog: SandboxWatchdog) -> None:
        sandbox = _make_sandbox()
        # Should not raise
        await watchdog._execute(sandbox, "reconfigure_model", {})

    async def test_clone_repo_calls_post(self, watchdog: SandboxWatchdog) -> None:
        sandbox = _make_sandbox(host="localhost", port=8080)
        payload = {"slug": "repo1", "clone_url": "https://github.com/x/y"}

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await watchdog._execute(sandbox, "clone_repo", payload)

        mock_client.post.assert_called_once_with(
            "http://localhost:8080/repos/clone", json=payload
        )
        mock_response.raise_for_status.assert_called_once()

    async def test_remove_repo_calls_delete(self, watchdog: SandboxWatchdog) -> None:
        sandbox = _make_sandbox(host="localhost", port=8080)
        payload = {"slug": "myrepo"}

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await watchdog._execute(sandbox, "remove_repo", payload)

        mock_client.delete.assert_called_once_with(
            "http://localhost:8080/repos/myrepo", params=payload
        )

    async def test_update_git_auth_calls_post(self, watchdog: SandboxWatchdog) -> None:
        sandbox = _make_sandbox(host="localhost", port=8080)
        payload = {"provider_type": "github", "token": "ghp_xxx"}

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await watchdog._execute(sandbox, "update_git_auth", payload)

        mock_client.post.assert_called_once_with(
            "http://localhost:8080/git-auth", json=payload
        )
