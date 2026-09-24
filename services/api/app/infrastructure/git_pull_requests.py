"""Abre Pull Requests no provedor git do repositório (GitHub ou Azure DevOps)."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from urllib.parse import quote, unquote

import httpx

_GITHUB_RE = re.compile(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$")
# https://[user@]dev.azure.com/{org}/{project}/_git/{repo}
_AZURE_RE = re.compile(r"dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/?#]+?)(?:\.git)?/?$")
# https://{org}.visualstudio.com/[DefaultCollection/]{project}/_git/{repo}
_AZURE_VS_RE = re.compile(
    r"([^/@.]+)\.visualstudio\.com/(?:DefaultCollection/)?([^/]+)/_git/([^/?#]+?)(?:\.git)?/?$"
)


class PullRequestError(RuntimeError):
    """Falha ao abrir o PR (URL não suportada, sem token ou erro do provedor)."""


@dataclass(frozen=True)
class PullRequestTarget:
    provider: str  # "github" | "azure_devops"
    # GitHub: "owner/repo". Azure: "org/project/repo".
    repo_path: str


@dataclass(frozen=True)
class PullRequestResult:
    provider: str
    repo_path: str
    url: str
    number: int


def parse_pr_target(clone_url: str) -> PullRequestTarget:
    """Identifica provedor e repositório pela URL de clone."""
    url = (clone_url or "").strip()
    if m := _GITHUB_RE.search(url):
        return PullRequestTarget("github", m.group(1))
    if m := _AZURE_RE.search(url) or _AZURE_VS_RE.search(url):
        return PullRequestTarget("azure_devops", "/".join(m.groups()))
    raise PullRequestError(f"Provedor git não suportado para PR: {url or '(sem URL)'}")


async def open_pull_request(
    target: PullRequestTarget,
    *,
    token: str,
    head: str,
    base: str,
    title: str,
    body: str,
    draft: bool = False,
) -> PullRequestResult:
    if not token:
        raise PullRequestError(f"Sem token do git provider para {target.repo_path}.")
    if target.provider == "github":
        return await _github(target, token, head, base, title, body, draft)
    return await _azure(target, token, head, base, title, body, draft)


async def _github(
    target: PullRequestTarget, token: str, head: str, base: str, title: str, body: str, draft: bool
) -> PullRequestResult:
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            f"https://api.github.com/repos/{target.repo_path}/pulls",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            json={"title": title, "body": body, "head": head, "base": base, "draft": draft},
        )
    if resp.status_code not in (200, 201):
        raise PullRequestError(f"GitHub API error {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    return PullRequestResult("github", target.repo_path, data.get("html_url", ""), data["number"])


async def _azure(
    target: PullRequestTarget, token: str, head: str, base: str, title: str, body: str, draft: bool
) -> PullRequestResult:
    # Nomes com espaço chegam codificados na URL de clone (%20).
    org, project, repo = (unquote(part) for part in target.repo_path.split("/"))
    api = (
        f"https://dev.azure.com/{quote(org)}/{quote(project)}/_apis/git/repositories/"
        f"{quote(repo)}/pullrequests?api-version=7.1"
    )
    basic = base64.b64encode(f":{token}".encode()).decode()
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            api,
            headers={"Authorization": f"Basic {basic}"},
            json={
                "sourceRefName": f"refs/heads/{head}",
                "targetRefName": f"refs/heads/{base}",
                "title": title,
                "description": body[:4000],
                "isDraft": draft,
            },
        )
    if resp.status_code not in (200, 201):
        raise PullRequestError(f"Azure DevOps API error {resp.status_code}: {resp.text[:500]}")
    number = resp.json()["pullRequestId"]
    web = (
        f"https://dev.azure.com/{quote(org)}/{quote(project)}/_git/{quote(repo)}"
        f"/pullrequest/{number}"
    )
    return PullRequestResult("azure_devops", target.repo_path, web, number)
