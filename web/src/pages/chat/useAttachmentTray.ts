import { useCallback, useRef, useState } from 'react'
import { deleteAttachment, uploadAttachment, type AiModel } from '../../api'
import type { TrayItem } from '../../components/AttachmentTray'
import {
  attachmentValidationError,
  isImageFile,
  modelIdForAttachments,
  modelSwitchNotice,
  normalizedClipboardFile,
} from './attachments'
import { randomId } from './formatting'

type AttachmentTrayParams = {
  token: string
  activeId: string | null
  models: AiModel[]
  onClaudeCli: boolean
  selectedModelId: string
  setSelectedModelId: (id: string) => void
}

/** Tray de anexos: validação, upload imediato ou pendente, remoção, colar e soltar. */
export function useAttachmentTray({
  token, activeId, models, onClaudeCli, selectedModelId, setSelectedModelId,
}: AttachmentTrayParams) {
  // Anexos pendentes de envio (uploads em curso, concluídos ou falhados).
  // Apenas itens `kind === 'uploaded'` viajam no payload do streamAssistantReply.
  const [trayItems, setTrayItems] = useState<TrayItem[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  // Aviso de troca automática de modelo por causa de imagem; some ao fechar ou ao trocar o modelo.
  const [modelNotice, setModelNotice] = useState<string | null>(null)
  const notifyModelSwitch = useCallback(
    (fromModelId: string, toModelId: string) =>
      setModelNotice(modelSwitchNotice(models, fromModelId, toModelId)),
    [models],
  )
  const dismissModelNotice = useCallback(() => setModelNotice(null), [])
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  /**
   * Faz upload de anexos/artefatos, registando placeholders na tray enquanto
   * a Promise resolve. Sem conversa ativa, mantém os arquivos como pendentes
   * para a primeira mensagem da tela inicial.
   */
  const uploadFiles = useCallback(
    (files: File[]) => {
      if (files.length === 0) return
      const normalized = files.map((file, index) => normalizedClipboardFile(file, index))
      const hasImage = normalized.some(isImageFile)
      const modelForImages = onClaudeCli ? '' : modelIdForAttachments(models, selectedModelId, hasImage)
      if (modelForImages && modelForImages !== selectedModelId) {
        setSelectedModelId(modelForImages)
        notifyModelSwitch(selectedModelId, modelForImages)
      }

      for (const file of normalized) {
        const validationError = attachmentValidationError(file)
        if (validationError) {
          setTrayItems((prev) => [
            ...prev,
            {
              kind: 'failed',
              localId: randomId(),
              filename: file.name,
              error: validationError,
            },
          ])
          continue
        }

        if (!activeId) {
          setTrayItems((prev) => [
            ...prev,
            {
              kind: 'pending',
              localId: randomId(),
              filename: file.name,
              file,
            },
          ])
          continue
        }

        const localId = randomId()
        const ctrl = new AbortController()
        setTrayItems((prev) => [
          ...prev,
          {
            kind: 'uploading',
            localId,
            filename: file.name,
            abort: () => ctrl.abort(),
          },
        ])
        uploadAttachment(token, activeId, file, ctrl.signal)
          .then((att) => {
            setTrayItems((prev) =>
              prev.map((it) =>
                it.localId === localId
                  ? { kind: 'uploaded', localId, attachment: att }
                  : it,
              ),
            )
          })
          .catch((e) => {
            if (e instanceof Error && e.name === 'AbortError') {
              setTrayItems((prev) => prev.filter((it) => it.localId !== localId))
              return
            }
            setTrayItems((prev) =>
              prev.map((it) =>
                it.localId === localId
                  ? {
                      kind: 'failed',
                      localId,
                      filename: file.name,
                      error: e instanceof Error ? e.message : String(e),
                    }
                  : it,
              ),
            )
          })
      }
    },
    // setSelectedModelId é o setter estável do useState; listado só para o lint.
    [activeId, models, onClaudeCli, selectedModelId, token, setSelectedModelId, notifyModelSwitch],
  )

  const uploadPendingAttachments = useCallback(
    async (conversationId: string): Promise<string[]> => {
      const pending = trayItems.filter(
        (item): item is Extract<TrayItem, { kind: 'pending' }> => item.kind === 'pending',
      )
      const attachmentIds: string[] = []
      for (const item of pending) {
        const ctrl = new AbortController()
        setTrayItems((prev) =>
          prev.map((it) =>
            it.localId === item.localId
              ? {
                  kind: 'uploading',
                  localId: item.localId,
                  filename: item.filename,
                  abort: () => ctrl.abort(),
                }
              : it,
          ),
        )
        try {
          const att = await uploadAttachment(token, conversationId, item.file, ctrl.signal)
          attachmentIds.push(att.id)
          setTrayItems((prev) =>
            prev.map((it) =>
              it.localId === item.localId
                ? { kind: 'uploaded', localId: item.localId, attachment: att }
                : it,
            ),
          )
        } catch (e) {
          setTrayItems((prev) =>
            prev.map((it) =>
              it.localId === item.localId
                ? {
                    kind: 'failed',
                    localId: item.localId,
                    filename: item.filename,
                    error: e instanceof Error ? e.message : String(e),
                  }
                : it,
            ),
          )
          throw e
        }
      }
      return attachmentIds
    },
    [token, trayItems],
  )

  /** Remove um item da tray; aborta uploads em curso e apaga uploads concluídos no backend. */
  const removeTrayItem = useCallback(
    (localId: string) => {
      const item = trayItems.find((it) => it.localId === localId)
      if (!item) return
      if (item.kind === 'uploading') item.abort()
      if (item.kind === 'uploaded' && activeId) {
        deleteAttachment(token, activeId, item.attachment.id).catch(() => {
          // melhor-esforço; o registo expira com a conversa via FK CASCADE
        })
      }
      setTrayItems((prev) => prev.filter((it) => it.localId !== localId))
    },
    [trayItems, activeId, token],
  )

  /** Limpa a tray sem chamar DELETE; anexos ficam vinculados ao historico. */
  const clearTrayLocal = useCallback(() => setTrayItems([]), [])

  /** Handler para input file e drag&drop. */
  const handleFileSelection = useCallback(
    (fileList: FileList | null | undefined) => {
      if (!fileList || fileList.length === 0) return
      const files = Array.from(fileList)
      uploadFiles(files)
    },
    [uploadFiles],
  )

  /** Handler para colar imagem do clipboard (Ctrl+V no textarea). */
  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const items = e.clipboardData?.items
      if (!items) return
      const images: File[] = []
      for (let i = 0; i < items.length; i++) {
        const it = items[i]
        if (it.kind === 'file' && it.type.startsWith('image/')) {
          const f = it.getAsFile()
          if (f) images.push(f)
        }
      }
      if (images.length > 0) {
        e.preventDefault()
        uploadFiles(images)
      }
    },
    [uploadFiles],
  )

  return {
    trayItems, setTrayItems, isDragOver, setIsDragOver, fileInputRef,
    uploadPendingAttachments, removeTrayItem, clearTrayLocal, handleFileSelection, handlePaste,
    modelNotice, notifyModelSwitch, dismissModelNotice,
  }
}

export type AttachmentTrayState = ReturnType<typeof useAttachmentTray>
