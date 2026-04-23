import hashlib
import re

from _grpc_session import PendingAction


def stable_chat_id(messages: list[dict]) -> str:
    """SHA-1 of the first user message → stable chat identifier."""
    first = next(
        (m.get("content", "") for m in messages if m.get("role") == "user"),
        "",
    )
    if isinstance(first, list):
        first = " ".join(p.get("text", "") for p in first if isinstance(p, dict))
    return hashlib.sha1(first[:300].encode()).hexdigest()[:16]


def user_id_from_body(body: dict) -> str:
    """
    Resolve o ID do utilizador para o par (user_id, chat_id).
    """
    raw = body.get("user")
    if raw is None:
        return str(body.get("user_id") or "anonymous")
    if isinstance(raw, dict):
        return str(raw.get("id") or body.get("user_id") or "anonymous")
    return str(raw)


def format_action(action: PendingAction) -> str:
    """
    Render an ActionRequired event as a clean chat message with visible choices.
    """
    lines = ["\n\n---\n"]

    if action.is_confirmation:
        lines.append("**O agente precisa da sua confirmação:**\n")
        lines.append(f"> {action.question}\n\n")
        lines.append("Responda:\n")
        lines.append("- **`sim`** — prosseguir\n")
        lines.append("- **`não`** — cancelar\n")

    else:
        lines.append("**O agente precisa de mais informações:**\n")
        clean_q = re.sub(r"\s*\[[^\]]+\]", "", action.question).strip()
        lines.append(f"> {clean_q}\n")

        if action.choices:
            lines.append("\nEscolha uma das opções:\n\n")
            for i, choice in enumerate(action.choices, 1):
                lines.append(f"**{i}.** {choice}\n")
            lines.append(
                f"\n_Digite o número ou o nome da opção (ex: `1` ou `{action.choices[0]}`)_\n"
            )
        else:
            lines.append("\nDigite sua resposta na caixa abaixo.\n")

    lines.append("\n---\n")
    return "".join(lines)
