# Tasks: GitHub MCP Access

## Phase 1: Setup

- [x] T001 Create feature spec, checklist, and plan in `specs/005-github-mcp-access/`

## Phase 2: Implementation

- [x] T002 Add GitHub MCP wrapper script in `services/sandbox/github_mcp_server_wrapper.sh`
- [x] T003 Install official GitHub MCP binary in `services/sandbox/Dockerfile`
- [x] T004 Seed default `github` MCP for `cappycloud-sandbox` in `services/api/alembic/versions/20260622_120000_seed_default_github_mcp.py`
- [x] T005 Add sandbox MCP export coverage for the GitHub wrapper in `services/api/tests/unit/use_cases/test_sandbox_mcps.py`
- [x] T006 Document preinstalled GitHub MCP in `services/sandbox/CLAUDE.md`

## Phase 3: Validation

- [x] T007 Run focused API MCP unit tests from `services/api`
- [x] T008 Review security risk for token handling
