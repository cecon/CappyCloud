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
- o sandbox mantem baselines persistentes por usuario em
  `/repos/users/<user>/<sandbox>/<repo>/<branch>`;
- o sandbox cria worktrees isolados de conversa em
  `/repos/sessions/<session_id>/<alias>`;
- cada conversa tambem carrega seu modo de permissao ativo;
- a sessao pode ser removida depois do TTL sem apagar historico da conversa;
- o agente deve usar skills do repositorio, MCPs ativos e docs disponiveis no
  ambiente atual.

## Workspaces persistentes por usuario

O baseline persistente e uma area preparada por usuario, repositorio, sandbox e
branch base. Ele reduz a preparacao repetida quando o mesmo usuario abre novas
conversas para o mesmo repositorio.

Esse baseline nao e o diretorio de trabalho do agente quando ha uma sessao de
conversa ativa. Antes da chamada gRPC, o `session_server` cria ou reaproveita o
worktree de conversa em `/repos/sessions/<session_id>/<alias>` a partir de um
baseline limpo. Assim, edicoes, diffs, branches de PR e arquivos temporarios
continuam presos ao worktree da conversa.

Se o baseline registrado nao existir mais no volume, o proximo uso chama
`/user-workspaces/ensure` no sandbox para recriar ou reparar o workspace. Se o
acesso do usuario ao repositorio foi revogado, a API deve negar a preparacao em
vez de reaproveitar paths antigos.

## Skills

Skills globais nao devem substituir conhecimento de repositorio.

Quando a pergunta envolve um repo selecionado, o agente deve carregar as skills
ativas daquele repositorio a partir do banco. Isso evita respostas genericas e
permite que cada ambiente mantenha instrucoes especificas: regras de negocio,
arquivos importantes, fontes obrigatorias, XMLs de banco e formato esperado de
resposta.

## Agentes arquiteturais por repositorio

Agentes arquiteturais tambem sao configuracao do ambiente, nao seed fixo do
produto.

Quando uma conversa seleciona repositorios, o pipeline procura em
`sandbox_agents` da sandbox ativa por agents habilitados com a convencao
`<repo-slug-normalizado>-architect`. Exemplos:

- repo `autosystem` -> agent `autosystem-architect`;
- repo `Seller` -> agent `seller-architect`;
- repo `smartpos` -> agent `smartpos-architect`.

Se o agent existir, seu `system_prompt` entra no prompt antes das skills do
repositorio. Se nao existir, o fluxo segue normalmente so com worktree, skills,
MCPs e documentacao externa disponiveis.

Nao crie migration para cadastrar agentes de projetos especificos. Cada sandbox
ou ambiente deve cadastrar seus proprios `SandboxAgent`s via API/admin ou setup
operacional.

## Modo de permissao por sessao

O modo de permissao do agente e uma configuracao da conversa. A UI pode enviar:

- `request_permissions`: fluxo normal, com prompts de permissao do OpenClaude;
- `accept_edits`: autoaprova ferramentas de edicao dentro dos limites do
  CappyCloud;
- `plan`: bloqueia acoes mutantes e preserva planejamento/leitura;
- `auto`: autoaprova prompts do OpenClaude;
- `bypass_permissions`: acesso completo, executando ações sem pedir confirmação.

Quando a conversa, preferencia ou runtime nao envia um valor valido, o fallback
padrao e `bypass_permissions` (**Acesso completo**).

Esse valor e salvo em `Conversation.permission_mode`, entra no body do stream e
chega ao OpenClaude por `ChatRequest.permission_mode`. Variaveis globais antigas
de autoaprovacao nao devem decidir permissao, porque uma sandbox atende varias
conversas e o comportamento precisa ser visivel na UI da sessao ativa.

Os limites duros nao dependem do modo selecionado: autorizacao de repositorio,
worktree da conversa, isolamento Docker, redacao de segredos e gates explicitos
para push, PR, deploy, rede ou mudancas de container continuam valendo.

Quando o runtime confirmar um aviso upstream sobre permissoes permissivas, o
agente deve enviar somente metadata sanitizada
`status.metadata.permission_warning.runtime_confirmed=true`. Nao envie logs
brutos, prompts ocultos, chaves, conteudo de repositorio ou inputs de ferramenta
para a UI.

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

## OpenClaude v0.17.1

O runtime da sandbox deve ficar pinado no tag SHA
`1b7e55058cca57f2f83d7e229441631794286c1a`, correspondente ao alvo
OpenClaude v0.17.1 verificado em `refs/tags/v0.17.1`. A release v0.18.0 existe
em upstream, mas fica fora desta atualizacao para manter o escopo da spec
`004-openclaude-v017-ui-debt`.

Recursos novos do OpenClaude que envolvam cache de conversa, persistencia de
sessao, descoberta de modelos, fallback de provider ou skills via `skill://`
devem continuar subordinados ao contexto autorizado do CappyCloud. Historico,
repositorios selecionados, modo de permissao, modelo visivel, uso e custo
continuam vindo da conversa, do banco e do catalogo autorizado.

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
