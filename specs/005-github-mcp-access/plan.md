# Implementation Plan: GitHub MCP Access

## Summary

Instalar o servidor oficial GitHub MCP como binário local no sandbox, expor um wrapper que usa `GITHUB_PERSONAL_ACCESS_TOKEN` ou `GITHUB_TOKEN`, e cadastrar um MCP `github` padrão para a sandbox `cappycloud-sandbox` sem sobrescrever configurações existentes.

## Technical Context

- Runtime alvo: `services/sandbox/Dockerfile`
- Configuração MCP: `mcp_servers` por sandbox, exportada para `mcpServers`
- Materialização: `services/cappycloud_agent/_pipeline_helpers.py` envia `/mcp/configure`
- Fonte externa verificada: repositório oficial `github/github-mcp-server`, que documenta `github-mcp-server stdio` com `GITHUB_PERSONAL_ACCESS_TOKEN`; Docker não é apropriado aqui porque a própria documentação do sandbox proíbe MCP via `docker run`. Release padrão fixado em `v1.4.0`, o release mais recente retornado pela página oficial em 2026-06-22.

## Constitution Check

- [x] Mudança não trivial tem spec, plano e tasks.
- [x] Configuração de MCP fica no banco e é materializada no sandbox.
- [x] Segurança: nenhum token real entra em código, migration ou documentação.
- [x] Gates planejados: testes unitários MCP e verificação de Dockerfile/documentação.

## Project Structure

### Documentation

- `specs/005-github-mcp-access/spec.md`
- `specs/005-github-mcp-access/tasks.md`
- `services/sandbox/CLAUDE.md`

### Source Code

- `services/sandbox/Dockerfile`
- `services/sandbox/github_mcp_server_wrapper.sh`
- `services/api/alembic/versions/*_seed_default_github_mcp.py`
- `services/api/tests/unit/use_cases/test_sandbox_mcps.py`

## Phase 0: Research

- Decision: usar o servidor oficial `github/github-mcp-server` como binário local.
- Rationale: a documentação oficial suporta binário local com `stdio`; o sandbox não disponibiliza Docker para MCPs.
- Alternatives considered: Docker image oficial, rejeitada por incompatibilidade com o sandbox; pacote npm antigo, rejeitado por não ser o caminho oficial atual.

## Phase 1: Design

- Instalar Go apenas em estágio de build e copiar o binário final para a imagem runtime, usando `GITHUB_MCP_REF=v1.4.0` por padrão.
- Wrapper local traduz `GITHUB_TOKEN` para `GITHUB_PERSONAL_ACCESS_TOKEN`.
- Migration insere o MCP `github` na sandbox padrão somente quando ele ainda não existe.

## Post-Design Constitution Check

- [x] Não há alteração de API pública.
- [x] Não há persistência de segredo novo.
- [x] Comportamento segue ADR-004: DB é fonte de verdade dos MCPs por sandbox.
