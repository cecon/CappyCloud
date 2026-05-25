import { Alert, Modal } from '@mantine/core'
import type { Repository } from '../api'
import { DocumentsPanel } from './DocumentsPanel'

type Props = {
  opened: boolean
  repository: Repository | null
  token: string
  onClose: () => void
}

export function RepositoryDocumentsModal({ opened, repository, token, onClose }: Props) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={repository ? `Documentos de ${repository.name}` : 'Documentos do repositório'}
      centered
      size="xl"
    >
      {repository && token ? (
        <DocumentsPanel
          token={token}
          repositoryId={repository.id}
          repositoryName={repository.name}
        />
      ) : (
        <Alert color="red" title="Sessão expirada">
          Faça login novamente para importar documentos.
        </Alert>
      )}
    </Modal>
  )
}
