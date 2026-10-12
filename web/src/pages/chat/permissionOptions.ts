import {
  DEFAULT_EXECUTION_PROFILE,
  DEFAULT_PERMISSION_MODE,
  type ExecutionProfile,
  type PermissionMode,
} from '../../api'
import type { ExecutionProfileOption, PermissionModeOption } from './types'

export const PERMISSION_MODE_OPTIONS: PermissionModeOption[] = [
  {
    value: 'request_permissions',
    label: 'Perguntar antes de agir',
    icon: 'shield',
    description: 'O agente pede confirmação para alterar algo',
    tone: 'safe',
  },
  {
    value: 'accept_edits',
    label: 'Aceitar edições',
    icon: 'edit_note',
    description: 'Alterações propostas podem ser aplicadas',
    tone: 'warn',
  },
  {
    value: 'plan',
    label: 'Modo de planejamento',
    icon: 'rule',
    description: 'Responde e planeja sem executar mudanças',
    tone: 'safe',
  },
  {
    value: 'auto',
    label: 'Modo automático',
    icon: 'bolt',
    description: 'Executa sem pedir, use com cuidado',
    tone: 'warn',
  },
  {
    value: 'bypass_permissions',
    label: 'Acesso completo',
    icon: 'warning',
    description: 'Permite executar ações sem pedir confirmação',
    tone: 'danger',
  },
]

const PERMISSION_MODE_VALUES = new Set<PermissionMode>(
  PERMISSION_MODE_OPTIONS.map((option) => option.value),
)

export const EXECUTION_PROFILE_OPTIONS: ExecutionProfileOption[] = [
  {
    value: 'medium',
    label: 'Medio',
    icon: 'bolt',
    description: 'Equilibra velocidade e confianca',
    searchBudget: 'ate 3 buscas amplas',
  },
  {
    value: 'fast',
    label: 'Rapido',
    icon: 'speed',
    description: 'Responde com investigacao curta',
    searchBudget: 'ate 2 buscas amplas',
  },
  {
    value: 'deep',
    label: 'Profundo',
    icon: 'travel_explore',
    description: 'Permite analise mais extensa',
    searchBudget: 'ate 6 buscas amplas',
  },
]

export function normalizePermissionMode(value: unknown): PermissionMode {
  return typeof value === 'string' && PERMISSION_MODE_VALUES.has(value as PermissionMode)
    ? (value as PermissionMode)
    : DEFAULT_PERMISSION_MODE
}

export function normalizeExecutionProfile(value: unknown): ExecutionProfile {
  return value === 'fast' || value === 'deep' || value === 'medium'
    ? value
    : DEFAULT_EXECUTION_PROFILE
}

export function permissionModeOption(mode: PermissionMode): PermissionModeOption {
  return PERMISSION_MODE_OPTIONS.find((option) => option.value === mode) ?? PERMISSION_MODE_OPTIONS[0]
}

export function executionProfileOption(profile: ExecutionProfile): ExecutionProfileOption {
  return EXECUTION_PROFILE_OPTIONS.find((option) => option.value === profile) ?? EXECUTION_PROFILE_OPTIONS[0]
}
