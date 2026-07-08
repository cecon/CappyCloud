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


def render_agentic_cycle_context(cycle_context: dict | None) -> str:
    if not cycle_context:
        return ""
    repository_ids = cycle_context.get("repository_ids") or []
    lines = [
        "## Contexto do ciclo Agentic Delivery",
        f"- Ciclo: `{cycle_context.get('cycle_id') or ''}`",
        f"- Pacote de trabalho: `{cycle_context.get('work_package_id') or ''}`",
        f"- Versão do pacote: `{cycle_context.get('work_package_version') or ''}`",
        f"- Domínio: `{cycle_context.get('domain_key') or 'não informado'}`",
        f"- Repositórios autorizados: {', '.join(f'`{r}`' for r in repository_ids)}",
        "",
        "Trate esta execução como review-only. Não faça push, deploy, merge, "
        "alteração irreversível ou chamada externa que mude estado. Produza "
        "evidências para afirmações importantes; quando faltar fonte, marque a "
        "afirmação como não suportada em vez de inferir.",
    ]
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

    parts.append(
        "\n### Sub-agente de investigação\n"
        "Para delegar uma investigação a um sub-agente especializado, executa via Bash:\n"
        "```bash\n"
        f"curl -s -X POST '{sandbox_session_url}/task' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        '  -d \'{"description":"<título>","prompt":"<instrução completa>"}\'\n'
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
        "'Grep...' ou 'Bash...' na resposta final.\n\n"
        "Enquanto estiver investigando, não escreva mensagens narrativas como 'vou verificar', "
        "'agora vou abrir' ou 'já tenho evidências'. Use as ferramentas silenciosamente e só "
        "produza texto quando tiver a resposta consolidada. Depois de chamar ferramentas, "
        "sempre finalize com uma resposta ao utilizador; nunca encerre apenas com plano, "
        "comandos usados ou resultados brutos de ferramenta.\n\n"
        "`Grep`, listagem de arquivos e busca textual servem para localizar candidatos; "
        "não são evidência suficiente para afirmar regra de negócio, procedimento, SQL, "
        "campo de tabela ou configuração. Antes de recomendar um procedimento ou citar um "
        "arquivo como prova, leia o trecho exato via Bash (`sed -n`, `nl -ba`, `cat` "
        "ou equivalente) e baseie a resposta somente em arquivos, linhas, schema ou "
        "documentação realmente abertos nesta conversa. Trechos de `documento importado` "
        "exibidos na seção de evidências automáticas já são documentação aberta; não "
        "reabra esses arquivos via ferramenta de leitura quando o bloco importado já "
        "trouxer tabela, coluna, PK ou flag necessária. "
        "Para perguntas de SQL/schema, um bloco importado `#### dbo.<tabela>` conta "
        "como schema comprovado; não substitua essa evidência por uma entidade do código "
        "se o próprio documento diferenciar cadastro legado/fiscal e camada SaaS. "
        "Se você só encontrou nomes de arquivos, diga que ainda não há evidência "
        "suficiente em vez de completar a resposta por inferência.\n\n"
        "Quando consultar documentação externa, inclua uma seção curta de fontes consultadas "
        "com o título e a URL das páginas realmente usadas. Quando cruzar com código, inclua "
        "também a evidência do repositório com arquivo e símbolo/trecho relevante. "
        "Não abra o diagnóstico com uma conclusão forte baseada em 'pelo código que consegui "
        "abrir' ou formulação equivalente sem listar logo abaixo ao menos uma evidência "
        "citável: arquivo e linha/símbolo, schema aberto, ou título e URL de documentação "
        "externa realmente consultada. Se a evidência ainda for parcial, diga que a análise "
        "é parcial e peça o log, fluxo executado, versão ou configuração que falta. "
        "Para casos de suporte operacional, prefira a estrutura: Diagnóstico, "
        "Evidências, Como corrigir, Como validar. Use como evidência documental "
        "apenas páginas cujo produto, módulo ou conteúdo trate diretamente do assunto "
        "investigado; ignore resultados de outros produtos quando eles forem apenas "
        "coincidência textual. Se a documentação não trouxer evidência direta, diga "
        "isso e sustente a resposta no código local.\n\n"
        "Para suporte operacional, não recomende `UPDATE`, alteração direta no banco, "
        "edição de XML ou manipulação de arquivo como correção principal, exceto se o "
        "utilizador pedir explicitamente uma intervenção técnica de banco. A orientação "
        "padrão deve ser por tela/configuração, sincronização/carga oficial da distribuidora, "
        "relatório/consulta de validação e coleta de log.\n\n"
        "Quando a pergunta pedir SQL, tabela, campo, flag, parâmetro ou configuração, "
        "confirme nomes reais em migrations, mappings, XML/Glade, seeds ou consultas "
        "existentes antes de responder. Se o schema não estiver comprovado, entregue "
        "uma consulta-modelo claramente marcada como template e peça o DDL/log necessário. "
        "Não invente nomes de colunas, flags de reprocessamento ou status sem evidência "
        "direta no código/schema lido.\n\n"
        "Para procedimento operacional, identifique primeiro a rotina oficial que o usuário "
        "deveria acionar: tela/view, endpoint, job configurado ou comando documentado. Se você "
        "leu apenas função interna, controller ou método de baixo nível, continue investigando "
        "quem chama essa rotina antes de transformar isso em passo operacional. Não recomende "
        "criar script novo, chamar função interna por shell, rodar código ad hoc ou contornar "
        "a UI/rotina oficial como caminho principal, salvo pedido explícito de automação "
        "técnica.\n\n"
        "Cite caminhos exatamente como aparecem no worktree ou na ferramenta. Não adicione "
        "prefixos como `src/`, pastas ou nomes de arquivo que não foram vistos no caminho lido.\n\n"
        "Se o pedido estiver fora do escopo técnico do repositório selecionado, responda "
        "em português de forma curta dizendo que atua no contexto técnico do produto/repositório "
        "e peça uma dúvida técnica."
    )
