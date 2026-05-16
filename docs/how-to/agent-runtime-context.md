# Contexto de execucao do agente

Este guia registra as decisoes operacionais que importam quando o CappyCloud
roda agentes contra repositorios de cliente, squads ou demonstracoes.

## Premissa principal

Repositorios nao sao infraestrutura fixa do deploy.

Cada ambiente pode cadastrar um conjunto diferente de repositorios, skills,
MCPs, modelos e fontes de documentacao. A conversa seleciona o contexto que
precisa, e o sandbox materializa esse contexto em uma sessao transitoria.

Na pratica:

- repositorios cadastrados no banco formam o catalogo do ambiente;
- cada conversa aponta para um ou mais repositorios desse catalogo;
- o sandbox cria worktrees em `/repos/sessions/<session_id>/<alias>`;
- a sessao pode ser removida depois do TTL sem apagar historico da conversa;
- o agente deve usar skills do repositorio, MCPs ativos e docs disponiveis no
  ambiente atual.

## Skills

Skills globais nao devem substituir conhecimento de repositorio.

Quando a pergunta envolve um repo selecionado, o agente deve carregar as skills
ativas daquele repositorio a partir do banco. Isso evita respostas genericas e
permite que cada ambiente mantenha instrucoes especificas: regras de negocio,
arquivos importantes, fontes obrigatorias, XMLs de banco e formato esperado de
resposta.

## Documentacao externa

Fontes como Confluence, observabilidade ou outras APIs devem entrar por
ferramentas configuradas no ambiente. O agente deve citar somente documentos que
consultou de fato, com titulo e URL reais quando a ferramenta retornar esses
campos.

Se a documentacao nao comprovar uma regra tecnica, a resposta deve dizer isso e
separar a evidencia do codigo da evidencia documental.

## Modelos e custo

O modelo usado na conversa deve ser dinamico. A configuracao do `.env` serve como
fallback operacional, mas a escolha da UI ou do banco precisa chegar ao
OpenRouter no momento da execucao.

O custo deve usar dados reais:

- usage retornado pelo provedor;
- tokens de cache reportados pelo provedor;
- preco atualizado via catalogo publico do OpenRouter para modelos cadastrados no
  ambiente.

Nao usar estimativa local de tokens como custo principal.

## Validacao antes de PR

Para mudancas que tocam agente, sandbox, API ou frontend, rode os checks que
existem no CI:

```bash
ruff check .
ruff format --check .
mypy app/
pytest
pnpm --dir web lint
pnpm --dir web build
```

Quando alguma ferramenta nao estiver instalada localmente, registre isso no PR e
rode o equivalente disponivel em Docker ou no ambiente do projeto.
