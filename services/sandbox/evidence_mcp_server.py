#!/usr/bin/env python3
"""Servidor MCP ``cappy`` (stdio, JSON por linha): evidências sob demanda.

O Claude CLI recebe este servidor a cada turno (claude_runtime_handler.js) com
o contexto da conversa em CAPPY_TOOL_CONTEXT: repositórios, worktrees e
Confluence de cada repo, e a raiz da sessão. As buscas chamam os endpoints do
próprio session server (/worktree/search, /skills/search, /confluence/search,
/memory/search, /workspaces/<slug>/knowledge/query).

A lógica vem de services/cappycloud_agent/_evidence_tool.py, copiado para a
imagem junto com os módulos ``_evidence_*``.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from typing import Any

SERVER_NAME = "cappycloud-evidence"
SERVER_VERSION = "0.1.0"

TOOLS = [
    {
        "name": "buscar_evidencias",
        "description": (
            "Procura no código dos repositórios da conversa e na documentação "
            "configurada (documentos importados e Confluence) o que tem a ver com "
            "a pergunta. Devolve só nomes: caminho dos arquivos e título/URL dos "
            "documentos. Use antes de investigar uma pergunta técnica sobre o "
            "produto; não use para conversa, saudação ou perguntas que não "
            "dependem do código ou da documentação."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pergunta": {
                    "type": "string",
                    "description": (
                        "A pergunta do usuário ou os termos a procurar (tabela, função, "
                        "parâmetro, mensagem de erro)."
                    ),
                },
                "com_trechos": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "true devolve também a linha encontrada em cada arquivo e o "
                        "conteúdo dos documentos importados. Use quando os nomes não "
                        "bastarem para decidir o que abrir."
                    ),
                },
            },
            "required": ["pergunta"],
        },
    },
    {
        "name": "consultar_conhecimento_workspace",
        "description": (
            "Consulta a memória do workspace (fatos confirmados em conversas "
            "anteriores) e o grafo de código da branch principal. Use no início "
            "de uma investigação para não refazer o que já se sabe."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pergunta": {"type": "string", "description": "O que você quer saber."},
            },
            "required": ["pergunta"],
        },
    },
]


def _context() -> dict[str, Any]:
    try:
        data = json.loads(os.environ.get("CAPPY_TOOL_CONTEXT") or "{}")
    except json.JSONDecodeError:
        data = {}
    port = os.environ.get("SESSION_SERVER_PORT") or "8080"
    return {
        "repos": [repo for repo in data.get("repos") or [] if isinstance(repo, dict)],
        "session_root": str(data.get("session_root") or ""),
        "session_url": str(data.get("session_url") or f"http://127.0.0.1:{port}"),
    }


def _tool_functions():
    from cappycloud_agent._evidence_tool import find_evidence, find_workspace_knowledge

    return find_evidence, find_workspace_knowledge


def call_tool(name: str, arguments: dict[str, Any], context: dict[str, Any]) -> str:
    find_evidence, find_workspace_knowledge = _tool_functions()
    question = str(arguments.get("pergunta") or "").strip()
    if not question:
        raise ValueError("Informe a pergunta.")
    if name == "buscar_evidencias":
        return asyncio.run(
            find_evidence(
                question,
                session_url=context["session_url"],
                repos=context["repos"],
                session_root=context["session_root"],
                with_excerpts=bool(arguments.get("com_trechos")),
            )
        )
    if name == "consultar_conhecimento_workspace":
        return asyncio.run(
            find_workspace_knowledge(
                question,
                session_url=context["session_url"],
                session_root=context["session_root"],
            )
        )
    raise KeyError(name)


def _result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(message: dict[str, Any], context: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if request_id is None:
        return None
    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        name = str(params.get("name") or "")
        if name not in {tool["name"] for tool in TOOLS}:
            return _error(request_id, -32601, f"Tool desconhecida: {name}")
        try:
            text = call_tool(name, params.get("arguments") or {}, context)
        except Exception as exc:
            return _result(
                request_id, {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
            )
        return _result(request_id, {"content": [{"type": "text", "text": text}]})
    return _error(request_id, -32601, f"Método não suportado: {method}")


def main() -> int:
    context = _context()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle(json.loads(line), context)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            continue
        if response is not None:
            # ASCII com escapes: não depende do encoding do stdout.
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
