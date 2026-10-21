/**
 * Cliente HTTP para a API CappyCloud (paths relativos `/api` com proxy Vite).
 *
 * Fachada: o código vive em `./api/`, separado por domínio.
 */

export * from './api/http'
export * from './api/auth'
export * from './api/adminDashboard'
export * from './api/preferences'
export * from './api/conversationTypes'
export * from './api/streamTypes'
export { parseStatusEvent } from './api/streamParsers'
export * from './api/conversations'
export * from './api/stream'
export * from './api/attachments'
export * from './api/environments'
export * from './api/workspaces'
export * from './api/repositories'
export * from './api/adminWorkspaces'
export * from './api/sandboxes'
export * from './api/sandboxTerminal'
export * from './api/models'
export * from './api/skills'
export * from './api/documents'
export * from './api/mcp'
export * from './api/globalSkills'
export * from './api/sandboxAgents'
export * from './api/access'
export * from './api/providers'
