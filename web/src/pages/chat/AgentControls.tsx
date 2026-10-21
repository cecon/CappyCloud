import type { ExecutionProfile, PermissionMode } from '../../api'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu'
import styles from '../../components/chat.module.css'
import {
  EXECUTION_PROFILE_OPTIONS,
  PERMISSION_MODE_OPTIONS,
  executionProfileOption,
  normalizePermissionMode,
  permissionModeOption,
} from './permissionOptions'

export function PermissionModeControl({
  value,
  onChange,
  disabled,
  runtimeConfirmed: _runtimeConfirmed,
  planModeEnabled,
  compact = false,
}: {
  value: PermissionMode
  onChange: (mode: PermissionMode) => void
  planModeEnabled: boolean
  disabled: boolean
  runtimeConfirmed: boolean
  compact?: boolean
}) {
  const option = permissionModeOption(value)
  const pillTone =
    option.tone === 'danger'
      ? styles.permissionModePillHigh
      : option.tone === 'warn'
        ? styles.permissionModePillCaution
        : ''

  return (
    <div className={`${styles.permissionModeControl} ${compact ? styles.permissionModeControlCompact : ''}`}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild disabled={disabled}>
          <button
            type="button"
            className={`${styles.permissionModePill} ${pillTone} ${disabled ? styles.permissionModePillDisabled : ''}`}
            title={disabled ? `${option.label} · bloqueado durante execução` : 'Modo de permissões'}
            aria-label="Modo de permissões"
            disabled={disabled}
          >
            <span className={`${styles.icon} ${styles.permissionModeIcon}`}>{option.icon}</span>
            <span className={styles.permissionModeLabel}>{option.label}</span>
            <span className={`${styles.icon} ${styles.permissionModeChevron}`}>expand_more</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align={compact ? 'start' : 'end'}
          sideOffset={8}
          className={styles.permissionModeMenu}
        >
          <DropdownMenuLabel className={styles.permissionModeMenuLabel}>
            Permissões do agente
          </DropdownMenuLabel>
          {PERMISSION_MODE_OPTIONS.filter((mode) => planModeEnabled || mode.value !== 'plan').map((mode) => {
            const selected = mode.value === value
            const toneClass =
              mode.tone === 'danger'
                ? styles.permissionModeMenuItemDanger
                : mode.tone === 'warn'
                  ? styles.permissionModeMenuItemWarn
                  : styles.permissionModeMenuItemSafe

            return (
              <DropdownMenuItem
                key={mode.value}
                className={`${styles.permissionModeMenuItem} ${toneClass} ${selected ? styles.permissionModeMenuItemSelected : ''}`}
                onClick={() => onChange(normalizePermissionMode(mode.value))}
              >
                <span className={`${styles.icon} ${styles.permissionModeMenuIcon}`}>{mode.icon}</span>
                <span className={styles.permissionModeMenuText}>
                  <span className={styles.permissionModeMenuTitle}>{mode.label}</span>
                  <span className={styles.permissionModeMenuDescription}>{mode.description}</span>
                </span>
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

export function ExecutionProfileControl({
  value,
  onChange,
  disabled,
  compact = false,
}: {
  value: ExecutionProfile
  onChange: (profile: ExecutionProfile) => void
  disabled: boolean
  compact?: boolean
}) {
  const option = executionProfileOption(value)

  return (
    <div className={`${styles.permissionModeControl} ${compact ? styles.permissionModeControlCompact : ''}`}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild disabled={disabled}>
          <button
            type="button"
            className={`${styles.permissionModePill} ${disabled ? styles.permissionModePillDisabled : ''}`}
            title={disabled ? `${option.label} · bloqueado durante execucao` : 'Perfil de execucao'}
            aria-label="Perfil de execucao"
            disabled={disabled}
          >
            <span className={`${styles.icon} ${styles.permissionModeIcon}`}>{option.icon}</span>
            <span className={styles.permissionModeLabel}>{option.label}</span>
            <span className={`${styles.icon} ${styles.permissionModeChevron}`}>expand_more</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align={compact ? 'start' : 'end'}
          sideOffset={8}
          className={styles.permissionModeMenu}
        >
          <DropdownMenuLabel className={styles.permissionModeMenuLabel}>
            Perfil de execucao
          </DropdownMenuLabel>
          {EXECUTION_PROFILE_OPTIONS.map((profile) => {
            const selected = profile.value === value
            return (
              <DropdownMenuItem
                key={profile.value}
                className={`${styles.permissionModeMenuItem} ${selected ? styles.permissionModeMenuItemSelected : ''}`}
                onClick={() => onChange(profile.value)}
              >
                <span className={`${styles.icon} ${styles.permissionModeMenuIcon}`}>{profile.icon}</span>
                <span className={styles.permissionModeMenuText}>
                  <span className={styles.permissionModeMenuTitle}>
                    {profile.label}
                    <span className={styles.permissionModeMenuDescription}> · {profile.searchBudget}</span>
                  </span>
                  <span className={styles.permissionModeMenuDescription}>{profile.description}</span>
                </span>
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
