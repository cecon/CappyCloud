import type { AccessibleWorkspace } from '../../api'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'
import styles from '../../components/chat.module.css'
import { rememberWorkspace } from './preferences'

/** Seletor de workspace da nova conversa e resumo dos repositórios dele. */
export function WorkspacePicker({
  projectWorkspaces,
  selectedWorkspaceId,
  setSelectedWorkspaceId,
  chosenWorkspace,
}: {
  projectWorkspaces: AccessibleWorkspace[]
  selectedWorkspaceId: string
  setSelectedWorkspaceId: (id: string) => void
  chosenWorkspace: AccessibleWorkspace | null
}) {
  return (
    <>
                {projectWorkspaces.length > 0 ? (
                  <Select
                    value={selectedWorkspaceId}
                    onValueChange={(id) => {
                      rememberWorkspace(id)
                      setSelectedWorkspaceId(id)
                    }}
                  >
                    <SelectTrigger
                      className={`${styles.contextSelectTrigger} ${styles.contextSelectTriggerSandbox} ${
                        chosenWorkspace ? '' : styles.contextPillRequired
                      }`}
                      title={
                        chosenWorkspace?.sandbox_name
                          ? `Workspace (roda na sandbox ${chosenWorkspace.sandbox_name})`
                          : 'Selecionar workspace'
                      }
                      aria-label="Selecionar workspace"
                    >
                      <span className={styles.icon} aria-hidden="true">
                        folder_open
                      </span>
                      <SelectValue placeholder="Workspace..." />
                    </SelectTrigger>
                    <SelectContent className={styles.contextSelectContent} position="item-aligned">
                      <SelectGroup>
                        <SelectLabel className={styles.contextSelectLabel}>Workspace</SelectLabel>
                        {projectWorkspaces.map((workspace) => (
                          <SelectItem
                            key={workspace.id}
                            value={workspace.id}
                            className={styles.contextSelectItem}
                            disabled={!workspace.ready}
                          >
                            {workspace.name}
                            {workspace.sandbox_name ? ` · ${workspace.sandbox_name}` : ''}
                            {workspace.ready ? '' : ' (sincronizando)'}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                ) : (
                  <div
                    className={`${styles.contextPill} ${styles.contextPillRequired}`}
                    title="Peça ao super admin acesso a um workspace"
                  >
                    <span className={styles.icon} style={{ fontSize: '0.875rem', opacity: 0.5 }}>folder_off</span>
                    <span className={styles.contextPillLabel} style={{ opacity: 0.6 }}>
                      Sem workspace — peça acesso ao super admin
                    </span>
                  </div>
                )}
                {chosenWorkspace && (
                  <div
                    className={styles.contextPill}
                    title={chosenWorkspace.repositories
                      .map((repo) => (repo.read_only ? `${repo.alias} (somente leitura)` : repo.alias))
                      .join(', ')}
                  >
                    <span className={styles.icon} style={{ fontSize: '0.875rem' }}>source</span>
                    <span className={styles.contextPillLabel}>
                      {chosenWorkspace.repositories.length}{' '}
                      {chosenWorkspace.repositories.length === 1 ? 'repositório' : 'repositórios'}
                    </span>
                  </div>
                )}
    </>
  )
}
