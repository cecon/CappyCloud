"""Prompt sections used by the CappyCloud agent context."""

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote


def _clean_confluence_labels(raw_labels: object) -> list[str]:
    if isinstance(raw_labels, str):
        values: Sequence[object] = raw_labels.split(",")
    elif isinstance(raw_labels, (list, tuple)):
        values = list(raw_labels)
    else:
        return []
    labels: list[str] = []
    seen: set[str] = set()
    for raw in values:
        label = str(raw).strip()
        key = label.lower()
        if label and key not in seen:
            seen.add(key)
            labels.append(label)
    return labels


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


def render_execution_profile(profile: str) -> str:
    normalized = profile if profile in {"fast", "medium", "deep"} else "medium"
    if normalized == "fast":
        return (
            "## Perfil de execucao\n\n"
            "Perfil selecionado: Rapido. Priorize resposta objetiva e alteracoes pequenas. "
            "Use no maximo 2 buscas/listagens amplas (`Grep`, `Glob`, `find`, `git ls-files`) "
            "antes de ler arquivos concretos. Se a evidencia ainda estiver incerta, entregue "
            "diagnostico parcial e peca o dado que destrava em vez de continuar explorando."
        )
    if normalized == "deep":
        return (
            "## Perfil de execucao\n\n"
            "Perfil selecionado: Profundo. Pode investigar mais quando o risco justificar, "
            "mas agrupe buscas por hipotese e evite repetir variacoes equivalentes. Depois de "
            "6 buscas/listagens amplas, pare para sintetizar o que ja foi encontrado antes de "
            "abrir uma nova frente."
        )
    return (
        "## Perfil de execucao\n\n"
        "Perfil selecionado: Medio. Equilibre velocidade e confianca. Comece com no maximo "
        "3 buscas/listagens amplas (`Grep`, `Glob`, `find`, `git ls-files`) por turno; depois "
        "leia arquivos concretos ja encontrados e avance. So faca novas buscas amplas quando "
        "a evidencia contradisser a hipotese ou quando o usuario pedir investigacao exaustiva."
    )


def render_repo_agents(agent_profiles: list[dict]) -> str:
    lines = ["## Agente arquitetural do repositório"]
    lines.append(
        "Estes perfis foram selecionados automaticamente pelo(s) repositório(s) "
        "da sessão. Use-os como estratégia de investigação e validação antes das skills."
    )
    for agent in agent_profiles:
        line = f"- **{agent['name']}** (`{agent['slug']}`)"
        if agent.get("description"):
            line += f" — {agent['description']}"
        if agent.get("default_model"):
            line += f"  \n  Modelo preferencial: `{agent['default_model']}`"
        lines.append(line)
        if agent.get("system_prompt"):
            lines.append(f"\n{agent['system_prompt']}")
    return "\n".join(lines)


def render_session_tools(
    sandbox_session_url: str, repos: list[dict] | None = None
) -> str:
    repo_ids = [
        str(repo.get("repo_id")).strip()
        for repo in (repos or [])
        if str(repo.get("repo_id") or "").strip()
    ]
    repo_filter = "".join(f"&repo_id={quote(repo_id, safe='')}" for repo_id in repo_ids)
    parts = [
        "## Ferramentas do servidor de sessão\n\n"
        "### Busca de documentação\n"
        "Para consultar mais documentação relevante, executa via Bash:\n"
        f"`curl -s '{sandbox_session_url}/skills/search?q=<termo>{repo_filter}'`\n"
        "(retorna JSON com slug/title/summary/content das skills mais próximas "
        "dentro do(s) repositório(s) da sessão).\n"
    ]

    confluence_repos = [
        repo for repo in (repos or []) if str(repo.get("confluence_url") or "").strip()
    ]
    if confluence_repos:
        lines = [
            "\n### Documentação externa por repositório\n",
            "Use Confluence apenas para os repositórios listados abaixo. Se um "
            "repositório não estiver listado aqui, não consulte `/confluence/*` para ele.",
            "Quando houver Confluence configurado, a consulta é obrigatória para "
            "perguntas de suporte operacional, configuração, cadastro, regra funcional, "
            "integração ou procedimento. Execute pelo menos uma busca em `/confluence/search` "
            "antes da resposta final e cite as páginas retornadas que forem usadas. "
            "Se nenhuma página relevante for encontrada, diga que a busca documental "
            "não trouxe evidência direta.",
        ]
        for repo in confluence_repos:
            alias = repo.get("alias") or repo.get("slug") or "repo"
            confluence_url = str(repo.get("confluence_url") or "").strip()
            confluence_space = str(repo.get("confluence_space") or "").strip()
            confluence_labels = _clean_confluence_labels(repo.get("confluence_labels"))
            encoded_url = quote(confluence_url, safe="")
            base_query = f"base_url={encoded_url}"
            filters: list[str] = []
            if confluence_space:
                encoded_space = quote(confluence_space, safe="")
                base_query = f"{base_query}&space={encoded_space}"
                filters.append(f"space `{confluence_space}`")
            primary_query = base_query
            label_query = ""
            if confluence_labels:
                encoded_labels = quote(",".join(confluence_labels), safe=",")
                label_query = f"{primary_query}&labels={encoded_labels}"
                labels_text = ", ".join(f"`{label}`" for label in confluence_labels)
                filters.append(f"labels {labels_text} (opcionais)")
            filter_label = f" ({'; '.join(filters)})" if filters else ""
            lines.append(
                f"- **{alias}**{filter_label}: `curl -s "
                f"'{sandbox_session_url}/confluence/search?{primary_query}&q=<termo>&limit=5'`"
            )
            if label_query:
                lines.append(
                    f"  Refinamento opcional com labels: `curl -s "
                    f"'{sandbox_session_url}/confluence/search?{label_query}&q=<termo>&limit=5'`"
                )
        any_space_configured = any(
            str(repo.get("confluence_space") or "").strip() for repo in confluence_repos
        )
        if any_space_configured:
            lines.append(
                "Quando o repositório tem `space` configurado, mantenha o parâmetro "
                "`&space=` em todas as buscas para esse repo — assim a busca fica "
                "restrita ao produto correto e não vaza para outros spaces do Confluence."
            )
        any_labels_configured = any(
            _clean_confluence_labels(repo.get("confluence_labels"))
            for repo in confluence_repos
        )
        if any_labels_configured:
            lines.append(
                "Quando usados, rótulos são parte do escopo documental, mas trate-os como "
                "refinamento opcional. A busca principal deve manter `&space=` e não precisa usar labels. "
                "Se usar `&labels=` e os resultados forem vazios, lentos ou pouco aderentes "
                "ao módulo perguntado, repita sem `&labels=` mantendo `&space=` e termos de "
                "busca mais curtos. Labels ajudam o escopo, mas podem estar incompletos."
            )
        lines.append(
            "Não use WebSearch como substituto do Confluence configurado; WebSearch não "
            "consulta essas credenciais nem respeita o space do repositório. Para dúvidas "
            "sobre parâmetros, cadastros, configurações, regras funcionais, integrações, "
            "procedimentos operacionais ou quando a pergunta pedir documentação externa, "
            "execute primeiro o `curl` de "
            "`/confluence/search` correspondente ao repositório da sessão."
        )
        lines.append(
            "Cruze o que vier da documentação externa com Grep e leitura via Bash "
            "(`sed -n`, `nl -ba`, `cat` ou equivalente) no repositório. Ao usar "
            "documentação, cite o título e a URL retornados. Nunca cite título, "
            "pageId ou conteúdo de fonte externa sem ter visto isso em resultado real "
            "nesta conversa."
        )
        parts.append("\n".join(lines))
    else:
        parts.append(
            "\n### Documentação externa\n"
            "Nenhum repositório desta sessão tem URL de Confluence configurada. "
            "Não consulte `/confluence/*` nesta execução; use apenas skills, código e "
            "outras MCPs explicitamente configuradas."
        )
    return "\n".join(parts)
