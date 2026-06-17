"""Renderização das evidências automáticas para o prompt do agente."""

from __future__ import annotations

from ._evidence_code import _active_parameter_dirs
from ._evidence_models import _CodeHit, _DocHit, _DocSearchAttempt, _ParameterDirectory
from ._evidence_terms import _parameter_numbers
from ._evidence_utils import _dedupe, _format_doc_filters, _worktree_path


def _parameter_lookup_guard(
    message: str,
    repos: list[dict],
    session_root: str,
    parameter_dirs: list[_ParameterDirectory] | None = None,
    docs: list[_DocHit] | None = None,
    doc_attempts: list[_DocSearchAttempt] | None = None,
) -> str:
    numbers = _parameter_numbers(message)
    if not numbers:
        return ""

    quoted_numbers = ", ".join(f"`{number}`" for number in numbers)
    active_dirs = _active_parameter_dirs(parameter_dirs or [])
    if active_dirs:
        path_lines = "\n".join(
            f"- `{directory.path}`" + (" (preferencial)" if directory.preferred else "")
            for directory in active_dirs
        )
        lookup_instruction = (
            "Procure o número, chave ou nome citado apenas nesses diretórios. "
            "Eles foram localizados nos arquivos rastreados do repo selecionado."
        )
    else:
        fallback_paths: list[str] = []
        for repo in repos or []:
            worktree = _worktree_path(repo, session_root)
            if worktree:
                fallback_paths.append(f"{worktree.rstrip('/')}/Parametros")
                fallback_paths.append(f"{worktree.rstrip('/')}/parameters")
        fallback_paths = _dedupe(fallback_paths)
        if not fallback_paths:
            return ""
        path_lines = "\n".join(f"- `{path}`" for path in fallback_paths)
        lookup_instruction = (
            "Primeiro tente localizar diretórios `*/Parametros` ou `*/parameters` "
            "dentro do repo selecionado e procure o número apenas nesses candidatos. "
            "Não pesquise o número na raiz inteira do repo."
        )

    lines = [
        "## Regra obrigatória para parâmetro numérico",
        f"A pergunta cita parâmetro numérico ({quoted_numbers}). Antes de responder, "
        "verifique a definição do parâmetro nos diretórios de parâmetros do repo:",
        path_lines,
        lookup_instruction,
        "Use `test -d`, `find` ou `Grep` com `path` apontando para esses diretórios. "
        "É permitido descobrir diretórios `Parametros`/`parameters`; não é permitido "
        "fazer busca ampla por `630` na raiz do repo.",
        "Se usar busca ampla por nomes de diretórios de parâmetros para descobrir "
        "candidatos, descreva isso como descoberta de diretórios, não como busca por "
        "`630` em todo o repositório.",
        "Se os diretórios não existirem ou se o número não for encontrado neles, diga que "
        "a definição do parâmetro não foi encontrada nesta cópia/branch.",
        "Nesse caso, não faça busca ampla no repositório para tentar inferir significado; "
        "buscas fora desse diretório só servem depois de encontrar a definição real do parâmetro.",
        "Não conclua o significado do parâmetro a partir de ocorrências soltas em NCM, "
        "CNPJ, Código IBGE, GUID, arquivos `.sln`, seeds ou outros dados que apenas "
        "contêm a sequência numérica.",
    ]
    doc_lines = _parameter_doc_result_lines(docs or [], doc_attempts or [])
    if doc_lines:
        lines.extend(doc_lines)
    lines.extend(
        [
            "Combine essa checagem com a seção de evidências automáticas. Se ela indicar "
            "Confluence sem resultados, diga isso na resposta final em vez de orientar o "
            "utilizador a consultar documentação oficial como se ela ainda não tivesse "
            "sido consultada.",
            "Depois de encontrar a definição real do parâmetro, aí sim procure usos no restante "
            "do repo para explicar impacto e comportamento.",
        ]
    )
    return "\n".join(lines)


def _parameter_doc_result_lines(
    docs: list[_DocHit],
    doc_attempts: list[_DocSearchAttempt],
) -> list[str]:
    if docs or not doc_attempts:
        return []
    lines = [
        "Documentação externa já consultada automaticamente para esta pergunta:",
    ]
    for attempt in doc_attempts[:4]:
        lines.append(
            f"- Confluence para `{attempt.query}`: sem resultados retornados"
            + _format_doc_filters(attempt.source)
            + "."
        )
    lines.append(
        "Na resposta final, cite essa ausência documental como fato confirmado; "
        "não escreva 'caso o Confluence não traga resultados' ou equivalente."
    )
    return lines


def _render_section(
    docs: list[_DocHit],
    code: list[_CodeHit],
    doc_attempts: list[_DocSearchAttempt] | None = None,
) -> str:
    if not docs and not code and not doc_attempts:
        return ""
    parts = [
        "## Evidências coletadas automaticamente",
        "Use esta amostra como ponto de partida obrigatório. As consultas de documentação "
        "listadas aqui já foram executadas pelo CappyCloud nesta conversa. Se a seção "
        "informar Confluence sem resultados, mencione essa ausência de evidência direta "
        "na resposta final; não diga apenas que o utilizador deve consultar documentação "
        "oficial. Se a amostra for insuficiente, continue investigando com Confluence, "
        "Grep e leitura via Bash (`sed -n`, `nl -ba`, `cat` ou equivalente) antes da "
        "resposta final. Não cite itens abaixo como conclusão sem validar o conteúdo "
        "relevante.",
    ]
    if docs:
        has_repo_docs = any(hit.source == "repository_document" for hit in docs)
        parts.append("### Documentação encontrada")
        doc_instruction = (
            "Os itens abaixo vieram das fontes documentais configuradas para o "
            "repositório: Confluence e/ou documentos importados indexados. "
            "Para pergunta de suporte, configuração, integração, procedimento "
            "ou schema importado, a resposta final deve incluir uma seção "
            "`Fontes consultadas` citando título e URL/origem dessas fontes. "
            "Não omita a fonte documental quando ela foi encontrada "
            "automaticamente."
        )
        if has_repo_docs:
            doc_instruction += (
                " Itens marcados como `documento importado` vieram de arquivos "
                "Markdown, PDF, DOCX, XLSX ou textos indexados no repositório; "
                "para perguntas sobre esses arquivos, priorize esses trechos "
                "antes de inferir pelo código. Esses itens já foram extraídos "
                "do índice documental do CappyCloud e os trechos exibidos aqui "
                "já contam como conteúdo aberto do documento. Para schema "
                "importado, blocos `#### dbo.<tabela>` abaixo são evidência "
                "direta de tabela, PK, coluna e flag; se eles responderem à "
                "pergunta, responda sem abrir arquivos com Grep ou comandos de leitura. "
                "Não tente provar a existência do arquivo no worktree com Grep ou "
                "comandos de leitura e não responda "
                "que o documento não foi localizado se esta seção trouxe trechos "
                "dele. Se um trecho importado apontar uma tabela provável, mas "
                "não trouxer as colunas ou flags necessárias, consulte novamente "
                "`/skills/search` com o nome exato da tabela, por exemplo "
                "`dbo.<tabela>`, antes de responder. Se a pergunta citar uma "
                "tabela específica, use apenas o "
                "bloco `#### dbo.<tabela>` correspondente dentro do trecho; não "
                "misture PKs ou colunas de tabelas vizinhas no mesmo chunk."
            )
        parts.append(doc_instruction)
        parts.extend(
            f"- `{hit.query}` → [{_doc_source_label(hit)}] {hit.title}"
            + (f" ({hit.url})" if hit.url else "")
            + (f": {hit.summary}" if hit.summary else "")
            for hit in docs
        )
    elif doc_attempts:
        parts.append("### Documentação consultada automaticamente sem resultados")
        parts.append(
            "Resultado documental já verificado: as buscas abaixo foram executadas e "
            "retornaram zero páginas. Na resposta final, trate isso como fato "
            "confirmado, não como hipótese. Não escreva 'caso a documentação não "
            "traga resultados'; escreva que o Confluence foi consultado com esses "
            "filtros e não trouxe evidência direta."
        )
        parts.extend(
            f"- `{attempt.query}` → Confluence sem resultados retornados"
            + _format_doc_filters(attempt.source)
            for attempt in doc_attempts[:8]
        )
    if code:
        parts.append("### Código encontrado")
        parts.extend(
            f"- `{hit.query}` → {hit.repo}:{hit.path}:{hit.line}: {hit.text}"
            for hit in code
        )
    return "\n".join(parts)


def _doc_source_label(hit: _DocHit) -> str:
    if hit.source == "repository_document":
        return "documento importado"
    return "Confluence"
