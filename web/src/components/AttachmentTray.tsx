/**
 * Bandeja de anexos pendentes na composição de mensagem.
 *
 * Mostra thumbnails dos anexos já enviados ao backend (com a descrição do
 * vision describer pronta) e dos uploads em progresso. Permite remover qualquer
 * item — uploads concluídos disparam DELETE no backend, em curso são abortados
 * via {@link UploadingAttachment.abort}.
 *
 * Integração: o `ChatPage` mantém o array de anexos no state e passa este
 * componente abaixo do textarea. Os ids dos anexos com `kind === 'uploaded'`
 * são enviados no payload de `streamAssistantReply`.
 */

import { useEffect, useMemo, useState } from 'react'
import type { Attachment } from '../api'
import { fetchAttachmentBlobUrl } from '../api'
import styles from './attachment-tray.module.css'

export interface UploadingAttachment {
  kind: 'uploading'
  /** id local apenas para UI (chave da lista). */
  localId: string
  filename: string
  abort: () => void
}

export interface UploadedAttachment {
  kind: 'uploaded'
  localId: string
  attachment: Attachment
}

export interface PendingAttachment {
  kind: 'pending'
  localId: string
  filename: string
  file: File
}

export interface FailedAttachment {
  kind: 'failed'
  localId: string
  filename: string
  error: string
}

export type TrayItem = PendingAttachment | UploadingAttachment | UploadedAttachment | FailedAttachment

interface Props {
  items: TrayItem[]
  token: string
  conversationId: string | null
  onRemove: (localId: string) => void
}

/**
 * Componente de thumbnail individual com lazy-load do Object URL.
 */
function Thumbnail({
  token,
  conversationId,
  attachment,
}: {
  token: string
  conversationId: string
  attachment: Attachment
}): React.JSX.Element {
  const [src, setSrc] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let url: string | null = null
    fetchAttachmentBlobUrl(token, conversationId, attachment.id)
      .then((u) => {
        if (cancelled) {
          URL.revokeObjectURL(u)
          return
        }
        url = u
        setSrc(u)
      })
      .catch(() => setSrc(null))
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [token, conversationId, attachment.id])

  if (!src) {
    return <div className={styles.thumbnailSkeleton} />
  }
  return <img src={src} alt={attachment.original_filename} className={styles.thumbnailImg} />
}

function AttachmentIcon({ attachment }: { attachment: Attachment }) {
  const icon =
    attachment.kind === 'pdf'
      ? 'picture_as_pdf'
      : attachment.kind === 'log'
        ? 'receipt_long'
        : attachment.kind === 'docx'
          ? 'description'
          : 'article'
  return (
    <div className={styles.fileThumb} aria-label={attachment.kind}>
      <span className={styles.fileIcon}>{icon}</span>
    </div>
  )
}

function PendingFileIcon({ file }: { file: File }) {
  const ext = file.name.toLowerCase()
  const icon =
    ext.endsWith('.pdf')
      ? 'picture_as_pdf'
      : ext.endsWith('.log')
        ? 'receipt_long'
        : ext.endsWith('.docx')
          ? 'description'
          : 'article'
  return (
    <div className={styles.fileThumb} aria-label={file.type || 'arquivo'}>
      <span className={styles.fileIcon}>{icon}</span>
    </div>
  )
}

function isPendingImage(file: File): boolean {
  const name = file.name.toLowerCase()
  return (
    file.type.startsWith('image/') ||
    name.endsWith('.png') ||
    name.endsWith('.jpg') ||
    name.endsWith('.jpeg') ||
    name.endsWith('.webp') ||
    name.endsWith('.gif')
  )
}

function PendingImageThumbnail({ file }: { file: File }) {
  const src = useMemo(() => URL.createObjectURL(file), [file])

  useEffect(() => {
    return () => URL.revokeObjectURL(src)
  }, [src])

  return <img src={src} alt={file.name} className={styles.thumbnailImg} />
}

function PendingThumbnail({ file }: { file: File }) {
  if (!isPendingImage(file)) return <PendingFileIcon file={file} />
  return <PendingImageThumbnail file={file} />
}

function statusLabel(attachment: Attachment): string {
  if (attachment.kind === 'image') {
    return attachment.has_description ? 'descrita' : 'anexada'
  }
  if (attachment.processing_status === 'indexed') {
    return `indexado · ${attachment.chunks_count}`
  }
  if (attachment.processing_status === 'error') {
    return attachment.processing_error || 'erro'
  }
  return attachment.processing_status || 'anexado'
}

export function AttachmentTray({ items, token, conversationId, onRemove }: Props): React.JSX.Element | null {
  if (items.length === 0) return null

  return (
    <div className={styles.tray} role="list" aria-label="Anexos pendentes">
      {items.map((item) => {
        const filename =
          item.kind === 'uploaded' ? item.attachment.original_filename : item.filename
        return (
          <div key={item.localId} className={styles.item} role="listitem" title={filename}>
            <div className={styles.thumbWrap}>
              {item.kind === 'uploaded' && conversationId ? (
                item.attachment.kind === 'image' ? (
                  <Thumbnail
                    token={token}
                    conversationId={conversationId}
                    attachment={item.attachment}
                  />
                ) : (
                  <AttachmentIcon attachment={item.attachment} />
                )
              ) : item.kind === 'pending' ? (
                <PendingThumbnail file={item.file} />
              ) : item.kind === 'failed' ? (
                <div className={`${styles.thumbnailSkeleton} ${styles.error}`} aria-label="Falha">
                  <span className={styles.icon}>error</span>
                </div>
              ) : (
                <div className={styles.thumbnailSkeleton} aria-label="Carregando">
                  <span className={`${styles.icon} ${styles.spin}`}>progress_activity</span>
                </div>
              )}
              <button
                className={styles.removeBtn}
                onClick={() => onRemove(item.localId)}
                title="Remover anexo"
                type="button"
                aria-label={`Remover ${filename}`}
              >
                <span className={styles.icon}>close</span>
              </button>
            </div>
            <div className={styles.meta}>
              <span className={styles.filename}>{filename}</span>
              {item.kind === 'uploaded' && (
                <span className={styles.statusOk}>
                  {statusLabel(item.attachment)}
                </span>
              )}
              {item.kind === 'pending' && <span className={styles.statusPending}>pronto</span>}
              {item.kind === 'uploading' && <span className={styles.statusUp}>enviando…</span>}
              {item.kind === 'failed' && <span className={styles.statusErr}>{item.error}</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}
