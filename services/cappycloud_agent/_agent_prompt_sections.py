"""Prompt sections used by the CappyCloud agent context."""

from __future__ import annotations

from urllib.parse import quote


def render_repo_skills(skills: list[dict]) -> str:
    lines = ["## Skills configuradas para este repositório"]
    lines.append(
        "Estas skills foram cadastradas para o(s) repositório(s) da sessão. "
        "Use título e descrição como contexto operacional antes de responder ou alterar código. "
        "Não use skills globais do sandbox como substitutas das skills do repositório."
    )
    for skill in skills:
        line = f"- **{skill['title']}**"
        if skill.get("summary"):
            line += f" — {skill['summary']}"
        if skill.get("source_url"):
            line += f"  \n  Fonte: {skill['source_url']}"
        lines.append(line)
        if skill.get("content"):
            lines.append(f"\n{skill['content']}")
    return "\n".join(lines)


def render_session_tools(sandbox_session_url: str, repos: list[dict] | None = None) -> str:
    parts = [
        "## Ferramentas do servidor de sessão\n\n"
        "### Busca de documentação\n"
        "Para consultar mais documentação relevante, executa via Bash:\n"
        f"`curl -s '{sandbox_session_url}/skills/search?q=<termo>'`\n"
        "(retorna JSON com slug/title/summary/content das skills mais próximas).\n"
    ]

    confluence_repos = [
        repo for repo in (repos or []) if str(repo.get("confluence_url") or "").strip()
    ]
    if confluence_repos:
        lines = [
            "\n### Documentação externa por repositório\n",
            "Use Confluence apenas para os repositórios listados abaixo. Se um "
            "repositório não estiver listado aqui, não consulte `/confluence/*` para ele.",
        ]
        for repo in confluence_repos:
            alias = repo.get("alias") or repo.get("slug") or "repo"
            confluence_url = str(repo.get("confluence_url") or "").strip()
            encoded = quote(confluence_url, safe="")
            lines.append(
                f"- **{alias}**: `curl -s "
                f"'{sandbox_session_url}/confluence/search?base_url={encoded}&q=<termo>&limit=5'`"
            )
        lines.append(
            "Cruze o que vier da documentação externa com Grep/Read no repositório. "
            "Ao usar documentação, cite o título e a URL retornados. Nunca cite título, "
            "pageId ou conteúdo de fonte externa sem ter visto isso em resultado real nesta conversa."
        )
        parts.append("\n".join(lines))
    else:
        parts.append(
            "\n### Documentação externa\n"
            "Nenhum repositório desta sessão tem URL de Confluence configurada. "
            "Não consulte `/confluence/*` nesta execução; use apenas skills, código e "
            "outras MCPs explicitamente configuradas."
        )

    parts.append(
        "\n### Sub-agente de investigação\n"
        "Para delegar uma investigação a um sub-agente especializado, executa via Bash:\n"
        "```bash\n"
        f"curl -s -X POST '{sandbox_session_url}/task' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d '{\"description\":\"<título>\",\"prompt\":\"<instrução completa>\"}'\n"
        "```\n"
        "O campo `result` da resposta contém o texto produzido pelo sub-agente.\n"
        "Use `jq -r '.result'` para extrair apenas o texto."
    )
    return "\n".join(parts)


def render_response_rules() -> str:
    return (
        "## Regras de resposta\n\n"
        "Responda diretamente ao utilizador. A resposta final deve começar pelo diagnóstico, "
        "não pelo plano de investigação. Não inclua plano interno, checklist de investigação, "
        "nomes de ferramentas chamadas ou anotações como 'Search...', 'Find...', 'Open...', "
        "'Read...', 'Grep...' ou 'Bash...' na resposta final.\n\n"
        "Enquanto estiver investigando, não escreva mensagens narrativas como 'vou verificar', "
        "'agora vou abrir' ou 'já tenho evidências'. Use as ferramentas silenciosamente e só "
        "produza texto quando tiver a resposta consolidada.\n\n"
        "Quando consultar documentação externa, inclua uma seção curta de fontes consultadas "
        "com o título e a URL das páginas realmente usadas. Quando cruzar com código, inclua "
        "também a evidência do repositório com arquivo e símbolo/trecho relevante. "
        "Para casos de suporte operacional, prefira a estrutura: Diagnóstico, "
        "Evidências, Como corrigir, Como validar. Use como evidência documental "
        "apenas páginas cujo produto, módulo ou conteúdo trate diretamente do assunto "
        "investigado; ignore resultados de outros produtos quando eles forem apenas "
        "coincidência textual. Se a documentação não trouxer evidência direta, diga "
        "isso e sustente a resposta no código local.\n\n"
        "Para suporte operacional, não recomende `UPDATE`, alteração direta no banco, edição de XML "
        "ou manipulação de arquivo como correção principal, exceto se o utilizador pedir explicitamente "
        "uma intervenção técnica de banco. A orientação padrão deve ser por tela/configuração, "
        "sincronização/carga oficial da distribuidora, relatório/consulta de validação e coleta de log."
    )
