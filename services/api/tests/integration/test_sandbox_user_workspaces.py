from __future__ import annotations

import json
import os
import subprocess
import uuid

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SANDBOX_INTEGRATION") != "1",
    reason="requires running cappycloud-sandbox container",
)


def _sandbox(command: str) -> str:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "sandbox", "sh", "-lc", command],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_user_workspace_status_rejects_paths_outside_user_root() -> None:
    output = _sandbox(
        "curl -s -o /tmp/status.out -w '%{http_code}' "
        "'http://localhost:8080/user-workspaces/status?workspace_path=/tmp/bad'"
    )
    assert output.strip() == "400"


def test_user_workspace_ensure_is_idempotent_and_repairs_dirty_baseline() -> None:
    slug = f"smoke-{uuid.uuid4().hex[:8]}"
    workspace = f"/repos/users/smoke/default/{slug}/main"
    setup = (
        f"rm -rf /repos/{slug} {workspace}; "
        f"mkdir -p /repos/{slug}; "
        f"git -C /repos/{slug} init; "
        f"git -C /repos/{slug} config user.email smoke@test.local; "
        f"git -C /repos/{slug} config user.name Smoke; "
        f"echo initial > /repos/{slug}/README.md; "
        f"git -C /repos/{slug} add README.md; "
        f"git -C /repos/{slug} commit -m init >/dev/null"
    )
    _sandbox(setup)
    ensure = (
        "curl -s -X POST http://localhost:8080/user-workspaces/ensure "
        "-H 'Content-Type: application/json' "
        f"-d '{{\"slug\":\"{slug}\",\"base_branch\":\"master\","
        f"\"workspace_path\":\"{workspace}\",\"clone_url\":\"\"}}'"
    )
    first = _sandbox(ensure)
    assert '"status":"ready"' in first

    _sandbox(f"echo dirty >> {workspace}/README.md")
    second = _sandbox(ensure)

    assert '"action":"repaired"' in second
    status = _sandbox(f"git -C {workspace} status --porcelain")
    assert status.strip() == ""


def test_sessions_derived_from_same_baseline_stay_isolated() -> None:
    slug = f"smoke-{uuid.uuid4().hex[:8]}"
    workspace = f"/repos/users/smoke/default/{slug}/main"
    setup = (
        f"rm -rf /repos/{slug} {workspace} /repos/sessions/{slug}-a "
        f"/repos/sessions/{slug}-b; "
        f"mkdir -p /repos/{slug}; "
        f"git -C /repos/{slug} init; "
        f"git -C /repos/{slug} config user.email smoke@test.local; "
        f"git -C /repos/{slug} config user.name Smoke; "
        f"echo initial > /repos/{slug}/README.md; "
        f"git -C /repos/{slug} add README.md; "
        f"git -C /repos/{slug} commit -m init >/dev/null"
    )
    _sandbox(setup)
    ensure_body = json.dumps(
        {
            "slug": slug,
            "base_branch": "master",
            "workspace_path": workspace,
            "clone_url": "",
        }
    )
    ensure = (
        "curl -s -X POST http://localhost:8080/user-workspaces/ensure "
        "-H 'Content-Type: application/json' "
        f"-d '{ensure_body}'"
    )
    assert '"status":"ready"' in _sandbox(ensure)
    for suffix in ("a", "b"):
        session_id = f"{slug}-{suffix}"
        session_body = json.dumps(
            {
                "session_id": session_id,
                "session_root": f"/repos/sessions/{session_id}",
                "repos": [
                    {
                        "slug": slug,
                        "alias": "Repo",
                        "base_branch": "master",
                        "branch_name": f"cappy/{slug}/{suffix}",
                        "source_workspace_path": workspace,
                    }
                ],
            }
        )
        create_session = (
            "curl -s -X POST http://localhost:8080/sessions "
            "-H 'Content-Type: application/json' "
            f"-d '{session_body}'"
        )
        assert '"repos_created"' in _sandbox(create_session)

    _sandbox(f"echo changed >> /repos/sessions/{slug}-a/Repo/README.md")
    session_b_contents = _sandbox(f"cat /repos/sessions/{slug}-b/Repo/README.md")
    baseline_status = _sandbox(f"git -C {workspace} status --porcelain")

    assert "changed" not in session_b_contents
    assert baseline_status.strip() == ""
