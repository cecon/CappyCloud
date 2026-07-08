# Feature Specification: GitHub MCP Access

**Feature Branch**: `005-github-mcp-access`
**Created**: 2026-06-22
**Status**: Draft
**Input**: "preciso que o github esteja funcionando e acessível, crie um mcp para acessar o github"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Acessar GitHub por MCP no sandbox (Priority: P1)

Como usuário do CappyCloud, quero que o agente tenha um MCP GitHub disponível no sandbox para consultar repositórios, issues, pull requests e workflows quando uma conversa precisar desse contexto.

**Independent Test**: Em uma sandbox padrão com token GitHub configurado, iniciar uma conversa e confirmar que a configuração enviada ao OpenClaude contém um servidor MCP `github` executável sem Docker.

**Acceptance Scenarios**:

1. **Given** uma sandbox padrão existente, **When** a configuração MCP é exportada, **Then** existe um servidor `github` habilitado.
2. **Given** o sandbox recebeu `GITHUB_TOKEN`, **When** o MCP GitHub inicia, **Then** ele usa esse token para autenticar no GitHub.
3. **Given** o sandbox não tem Docker disponível, **When** o MCP GitHub é materializado, **Then** o comando não depende de `docker run`.

### Edge Cases

- Token GitHub ausente: o MCP pode aparecer configurado, mas chamadas autenticadas devem falhar de forma clara no servidor MCP.
- Sandbox já tem MCP `github` cadastrado: a migração não deve sobrescrever configuração administrada manualmente.
- Arquitetura amd64 ou arm64: o binário instalado no sandbox deve ser compatível com ambas.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A sandbox padrão deve receber um servidor MCP chamado `github`, habilitado por padrão, sem sobrescrever cadastro existente com o mesmo nome.
- **FR-002**: O MCP GitHub deve executar por binário local ou wrapper local, sem depender de Docker dentro do sandbox.
- **FR-003**: O MCP GitHub deve aceitar o token GitHub já usado pelo sandbox para operações Git, evitando nova configuração manual quando `GITHUB_TOKEN` estiver presente.
- **FR-004**: A configuração exportada para OpenClaude deve permanecer no formato `mcpServers`.
- **FR-005**: A documentação do sandbox deve listar o MCP GitHub como pré-instalado e explicar o requisito de token.

### Key Entities *(include if feature involves data)*

- **McpServer**: registro de servidor MCP por sandbox, com `name`, `command`, `args`, `env` e `enabled`.
- **Sandbox**: ambiente onde o MCP é materializado para uso pelo agente.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- O token não deve ser gravado no código ou na migração.
- O MCP deve herdar credenciais do ambiente do sandbox, especialmente `GITHUB_TOKEN`, com fallback para `GITHUB_PERSONAL_ACCESS_TOKEN`.
- Evidência principal deve vir de testes de exportação MCP, Dockerfile e documentação do sandbox.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- Em 100% das sandboxes padrão novas ou migradas sem MCP `github`, a exportação MCP inclui `github`.
- O comando do MCP GitHub não contém `docker`.
- A documentação do sandbox lista o MCP GitHub e as variáveis aceitas para autenticação.

## Assumptions

- O token GitHub operacional já chega ao sandbox como `GITHUB_TOKEN` ou `GITHUB_PERSONAL_ACCESS_TOKEN`.
- A instalação suportada pelo projeto deve preferir binário local porque o sandbox explicitamente não disponibiliza Docker.
