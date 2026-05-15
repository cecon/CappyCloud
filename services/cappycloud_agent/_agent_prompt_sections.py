"""Prompt sections used by the CappyCloud agent context."""

from __future__ import annotations


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


def render_session_tools(sandbox_session_url: str) -> str:
    return (
        "## Ferramentas do servidor de sessão\n\n"
        "### Busca de documentação\n"
        "Para consultar mais documentação relevante, executa via Bash:\n"
        f"`curl -s '{sandbox_session_url}/skills/search?q=<termo>'`\n"
        "(retorna JSON com slug/title/summary/content das skills mais próximas).\n\n"
        "### Confluence Linx Share\n"
        "Para perguntas sobre AutoSystem, consulte também a documentação pública Linx Share "
        "antes de concluir quando houver dúvida de configuração, mensagem de erro, tela, "
        "menu, módulo ou regra operacional. Use estes endpoints read-only via Bash:\n"
        f"- `curl -s '{sandbox_session_url}/confluence/main'`\n"
        f"- `curl -s '{sandbox_session_url}/confluence/search?q=<termo>&limit=5'`\n"
        f"- `curl -s '{sandbox_session_url}/confluence/page?id=<pageId>'`\n"
        "Cruze o que vier do Confluence com Grep/Read no repositório. Se não houver resultado "
        "relevante, tente mais 1-2 buscas com termos reduzidos e sinônimos de domínio antes "
        "de desistir. Exemplo: para Shell Select, tente também `shell select`, `Shell Box`, "
        "`Raízen`, `Ipiranga` e `IPP`. Ao usar documentação, cite o título e a URL retornados. "
        "Nunca cite título, pageId ou conteúdo de Confluence sem ter visto isso em resultado real "
        "de `/confluence/main`, `/confluence/search` ou `/confluence/page` nesta conversa.\n\n"
        "### Sub-agente de investigação\n"
        "Para delegar uma investigação a um sub-agente especializado, executa via Bash:\n"
        "```bash\n"
        f"curl -s -X POST '{sandbox_session_url}/task' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d '{\"description\":\"<título>\",\"prompt\":\"<instrução completa>\"}'\n"
        "```\n"
        "O campo `result` da resposta contém o texto produzido pelo sub-agente.\n"
        "Use `jq -r '.result'` para extrair apenas o texto."
    )


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
        "Quando consultar Confluence/Linx Share, inclua uma seção curta de fontes consultadas "
        "com o título e a URL das páginas realmente usadas. Quando cruzar com código, inclua "
        "também a evidência do repositório com arquivo e símbolo/trecho relevante. Para casos "
        "de suporte operacional, prefira a estrutura: Diagnóstico, Evidências, Como corrigir, "
        "Como validar. Para perguntas de AutoSystem, use como evidência documental apenas páginas "
        "do espaço/produto Postos/AutoSystem ou páginas cujo conteúdo trate diretamente do módulo "
        "investigado; ignore resultados de outros produtos como Millennium, Farma ou Shopping "
        "quando eles forem apenas coincidência textual. Se a documentação não trouxer evidência "
        "direta, diga isso e sustente a resposta no código local.\n\n"
        "Regra crítica para bloqueio de venda AutoSystem/Shell Select/IPP: não diga que "
        "`data_bloq_venda > hoje` bloqueia. Quando houver evidência de "
        "`data_bloq_venda`, explique como data de bloqueio atingida/vencida ou campo "
        "de bloqueio preenchido conforme a rotina consultada; se encontrar SQL como "
        "`data_bloq_venda > current_date OR data_bloq_venda IS NULL`, isso significa "
        "que data futura ou nula libera, e data atual/passada bloqueia. Se a página "
        "Confluence não citar `data_bloq_venda`, `permite_venda_dist` ou a tabela "
        "interna, trate a documentação apenas como contexto de Shell Box/AutoSystem e "
        "deixe claro que a causa técnica foi confirmada no código.\n\n"
        "Para suporte operacional, não recomende `UPDATE`, alteração direta no banco, edição de XML "
        "ou manipulação de arquivo como correção principal, exceto se o utilizador pedir explicitamente "
        "uma intervenção técnica de banco. A orientação padrão deve ser por tela/configuração, "
        "sincronização/carga oficial da distribuidora, relatório/consulta de validação e coleta de log."
    )
