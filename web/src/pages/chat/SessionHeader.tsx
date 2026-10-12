import type { AiModel } from '../../api'
import { ModelPicker } from '../../components/ModelPicker'
import styles from '../../components/chat.module.css'
import type { PrLink } from './types'

/** Session header — env + branch + diff stats + PR + modelo. */
export function SessionHeader({
  activeEnvSlug, activeEnvName, activeBaseBranch, activeSandboxName, headBranch,
  models, selectedModelId, setSelectedModelId, streaming,
  diffStats, prLoading, prLinks, prError, onCreatePr,
}: {
  activeEnvSlug: string | null
  activeEnvName: string | null
  activeBaseBranch: string | null
  activeSandboxName: string | null
  headBranch: string | null
  models: AiModel[]
  selectedModelId: string
  setSelectedModelId: (id: string) => void
  streaming: boolean
  diffStats: { added: number; removed: number } | null
  prLoading: boolean
  prLinks: PrLink[]
  prError: string | null
  onCreatePr: () => void
}) {
  const selectedModelLabel =
    models.find((model) => model.id === selectedModelId || model.model_id === selectedModelId)?.display_name ||
    selectedModelId ||
    'Modelo'
  const activeBranchLabel = headBranch ?? activeBaseBranch ?? 'develop'
  const sandboxLabel = activeSandboxName ?? 'Sandbox'

  return (
      <div className={styles.sessionHeader}>
        <div className={styles.sessionHeaderInner}>
          <div className={styles.sessionHeaderLeft}>
          {activeEnvSlug ? (
            <>
              <span className={`${styles.icon} ${styles.sessionHeaderIcon}`}>folder_open</span>
              <span className={styles.sessionHeaderEnv}>{activeEnvName ?? activeEnvSlug}</span>
              {activeBaseBranch && (
                // Só o ícone: o cabeçalho tem pouco espaço; o detalhe fica na dica.
                <span
                  className={styles.sessionHeaderBranch}
                  title={`Seu espaço isolado: as alterações ficam numa branch só desta conversa (base ${activeBranchLabel}).`}
                  aria-label={`Espaço isolado, base ${activeBranchLabel}`}
                >
                  <span className={`${styles.icon} ${styles.sessionHeaderBranchIcon}`}>account_tree</span>
                </span>
              )}
            </>
          ) : (
            <span className={styles.sessionHeaderEnv} style={{ opacity: 0.85 }}>
              Conversa (sem repositório ligado)
            </span>
          )}
          </div>
          <div className={styles.sessionHeaderRight}>
          <div className={styles.sessionPresenceChip} title="Sandbox desta conversa">
            <span className={styles.sessionPresenceAvatars}>
              <span className={styles.icon}>dns</span>
            </span>
            <span>{sandboxLabel}</span>
          </div>
          {models.length > 0 ? (
            <div className={styles.sessionHeaderModelPicker}>
              <ModelPicker
                models={models}
                value={selectedModelId}
                onChange={setSelectedModelId}
                disabled={streaming}
                compact
              />
            </div>
          ) : (
            <div className={styles.sessionModelChip} title={selectedModelLabel}>
              <span aria-hidden />
              {selectedModelLabel}
            </div>
          )}
          {diffStats && (diffStats.added > 0 || diffStats.removed > 0) && (
            <>
              <span className={styles.diffAdded}>+{diffStats.added}</span>
              <span className={styles.diffRemoved}>-{diffStats.removed}</span>
              {activeEnvSlug && (
                prLinks.length > 0 ? (
                  <>
                    {prLinks.map((pr) => (
                      <a
                        key={pr.url}
                        href={pr.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={styles.prLink}
                        title={pr.label ? `PR de ${pr.label}` : undefined}
                      >
                        <span className={`${styles.icon}`} style={{ fontSize: '0.875rem' }}>open_in_new</span>
                        {prLinks.length > 1 && pr.label ? `PR ${pr.label}` : 'Ver PR'}
                      </a>
                    ))}
                    {prError && (
                      <span role="alert" style={{ fontSize: '0.72rem', color: 'var(--destructive)' }} title={prError}>
                        falhou em parte
                      </span>
                    )}
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className={styles.createPrBtn}
                      onClick={onCreatePr}
                      disabled={prLoading || streaming}
                    >
                      {prLoading ? 'Criando…' : 'Criar PR'}
                    </button>
                    {prError && (
                      <span
                        role="alert"
                        style={{ fontSize: '0.72rem', color: 'var(--destructive)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        title={prError}
                      >
                        {prError}
                      </span>
                    )}
                  </>
                )
              )}
            </>
          )}
          </div>
        </div>
      </div>
  )
}
