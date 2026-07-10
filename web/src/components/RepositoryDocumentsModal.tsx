import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
    <Dialog open={opened} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="max-h-[88vh] max-w-[min(1120px,calc(100vw-2rem))] overflow-y-auto p-0">
        <DialogHeader className="border-b border-border px-6 py-5">
          <DialogTitle>
            {repository ? `Documentos de ${repository.name}` : 'Documentos do repositório'}
          </DialogTitle>
          <DialogDescription>
            Importação, reindexação, RAG e graph dos documentos carregados no repositório.
          </DialogDescription>
        </DialogHeader>
        <div className="px-6 pb-6">
          {repository && token ? (
            <DocumentsPanel
              token={token}
              repositoryId={repository.id}
              repositoryName={repository.name}
            />
          ) : (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
              Faça login novamente para importar documentos.
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
