import type { Attachment } from '../../api'
import { fetchAdminAttachmentBlobUrl, fetchAttachmentBlobUrl } from '../../api'
import { AttachmentIcon, type AttachmentSource, Thumbnail } from '../AttachmentTray'
import styles from '../attachment-tray.module.css'

/**
 * Anexos enviados com uma pergunta: miniatura para imagem, ícone para os
 * demais. Clicar abre o arquivo numa aba nova. Só leitura.
 */
export function MessageAttachments({
  attachments, token, conversationId, source = 'owner',
}: {
  attachments: Attachment[]
  token: string
  conversationId: string
  source?: AttachmentSource
}) {
  if (attachments.length === 0) return null

  async function openFile(attachment: Attachment) {
    // A aba abre já no clique: navegador bloqueia window.open depois de um await.
    const tab = window.open('', '_blank')
    try {
      const load = source === 'admin' ? fetchAdminAttachmentBlobUrl : fetchAttachmentBlobUrl
      const url = await load(token, conversationId, attachment.id)
      if (tab) tab.location.href = url
      else window.open(url, '_blank')
    } catch {
      tab?.close()
    }
  }

  return (
    <div className="mt-2 flex flex-wrap gap-2" role="list" aria-label="Anexos da mensagem">
      {attachments.map((attachment) => (
        <button
          key={attachment.id}
          type="button"
          role="listitem"
          className={`${styles.item} text-left`}
          title={`Abrir ${attachment.original_filename}`}
          onClick={() => void openFile(attachment)}
        >
          <div className={styles.thumbWrap}>
            {attachment.kind === 'image' ? (
              <Thumbnail
                token={token}
                conversationId={conversationId}
                attachment={attachment}
                source={source}
              />
            ) : (
              <AttachmentIcon attachment={attachment} />
            )}
          </div>
          <span className={styles.filename}>{attachment.original_filename}</span>
        </button>
      ))}
    </div>
  )
}
