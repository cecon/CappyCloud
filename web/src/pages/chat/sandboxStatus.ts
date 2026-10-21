import type { Sandbox } from '../../api'
import styles from '../../components/chat.module.css'

export function isSandboxAvailable(sandbox: Sandbox): boolean {
  return sandbox.status === 'active' && (
    sandbox.container_status === 'running' ||
    sandbox.container_status === 'configured'
  )
}

export function sandboxStatusLabel(sandbox: Sandbox): string {
  if (sandbox.status === 'offline') return 'Offline'
  if (sandbox.container_status === 'configured') return 'Configurada'
  if (sandbox.container_status === 'running') return 'Rodando'
  if (sandbox.container_status === 'starting') return 'Iniciando'
  if (sandbox.container_status === 'error') return 'Erro'
  if (sandbox.container_status === 'stopped') return 'Parada'
  if (sandbox.container_status === 'not_created') return 'Não criada'
  return sandbox.status || sandbox.container_status
}

export function sandboxStatusClass(sandbox: Sandbox): string {
  if (sandbox.container_status === 'error') return styles.sandboxStatusBadgeError
  if (isSandboxAvailable(sandbox)) return styles.sandboxStatusBadgeActive
  return styles.sandboxStatusBadgeMuted
}
