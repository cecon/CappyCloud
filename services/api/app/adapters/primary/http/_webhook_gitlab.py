"""GitLab-specific webhook handling logic."""

from __future__ import annotations


def build_gitlab_prompt(event_type: str, payload: dict) -> str | None:
    """Gera prompt para evento GitLab. Retorna None se ignorado."""
    if "Pipeline Hook" in event_type or event_type == "pipeline":
        obj = payload.get("object_attributes") or {}
        if obj.get("status") == "failed":
            builds = payload.get("builds") or []
            failed = [b.get("name") for b in builds if b.get("status") == "failed"]
            failed_str = ", ".join(failed) if failed else "desconhecido"
            return (
                f"Pipeline GitLab falhou. Jobs com falha: {failed_str}.\n"
                "Analise os logs e corrija o problema."
            )

    elif "Merge Request Hook" in event_type or event_type == "merge_request":
        obj = payload.get("object_attributes") or {}
        if obj.get("action") == "open":
            title = obj.get("title", "")
            description = obj.get("description") or ""
            iid = obj.get("iid", "")
            return (
                f"Foi aberto o Merge Request !{iid}: '{title}'.\n{description}\n\n"
                "Revise o MR acima."
            )

    elif "Push Hook" in event_type or event_type == "push":
        commits = payload.get("commits") or []
        last = commits[-1] if commits else {}
        message = last.get("message", "")[:200]
        ref = payload.get("ref", "")
        return (
            f"Push em {ref}: {message}\n\nVerifique se há problemas no código actualizado."
        )

    return None
