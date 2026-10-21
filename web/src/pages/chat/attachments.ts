import type { AiModel } from '../../api'
import type { TrayItem } from '../../components/AttachmentTray'
import {
  ALLOWED_ATTACHMENT_EXT,
  ALLOWED_ATTACHMENT_MIME,
  MAX_ARTIFACT_ATTACHMENT_BYTES,
  MAX_IMAGE_ATTACHMENT_BYTES,
} from './constants'
import { sortModelsForSelect } from './preferences'

function fileExtension(name: string): string {
  const idx = name.lastIndexOf('.')
  return idx >= 0 ? name.slice(idx).toLowerCase() : ''
}

function isSupportedAttachment(file: File): boolean {
  return (
    ALLOWED_ATTACHMENT_MIME.has(file.type) ||
    file.type.startsWith('text/') ||
    ALLOWED_ATTACHMENT_EXT.has(fileExtension(file.name))
  )
}

export function isImageFile(file: File): boolean {
  const ext = fileExtension(file.name)
  return file.type.startsWith('image/') || ['.png', '.jpg', '.jpeg', '.webp', '.gif'].includes(ext)
}

function attachmentLimitBytes(file: File): number {
  return isImageFile(file) ? MAX_IMAGE_ATTACHMENT_BYTES : MAX_ARTIFACT_ATTACHMENT_BYTES
}

export function attachmentValidationError(file: File): string | null {
  if (!isSupportedAttachment(file)) return 'Tipo não suportado'
  const limit = attachmentLimitBytes(file)
  if (file.size > limit) return `Acima de ${(limit / 1024 / 1024).toFixed(0)} MB`
  return null
}

function clipboardImageName(file: File, index: number): string {
  if (file.name.trim()) return file.name
  if (!file.type.startsWith('image/')) return `anexo-${index + 1}`
  if (file.type === 'image/jpeg') return `print-${index + 1}.jpg`
  if (file.type === 'image/webp') return `print-${index + 1}.webp`
  if (file.type === 'image/gif') return `print-${index + 1}.gif`
  return `print-${index + 1}.png`
}

export function normalizedClipboardFile(file: File, index: number): File {
  const name = clipboardImageName(file, index)
  if (name === file.name) return file
  return new File([file], name, {
    type: file.type || 'application/octet-stream',
    lastModified: file.lastModified || Date.now(),
  })
}

function isVisionModel(model: AiModel | undefined): boolean {
  return !!model?.capabilities?.includes('vision')
}

function preferredVisionModelId(models: AiModel[]): string {
  const visionModels = models.filter((model) => isVisionModel(model))
  return (
    visionModels.find((model) => model.is_default?.vision)?.model_id ||
    sortModelsForSelect(visionModels)[0]?.model_id ||
    ''
  )
}

export function modelIdForAttachments(
  models: AiModel[],
  selectedModelId: string,
  hasImage: boolean,
): string {
  if (!hasImage) return selectedModelId
  const selected = models.find((model) => model.model_id === selectedModelId)
  if (isVisionModel(selected)) return selectedModelId
  return preferredVisionModelId(models) || selectedModelId
}

export function isSendableTrayItem(item: TrayItem): boolean {
  return item.kind === 'pending' || item.kind === 'uploaded'
}

export function trayItemHasImage(item: TrayItem): boolean {
  if (item.kind === 'pending') return isImageFile(item.file)
  if (item.kind === 'uploaded') {
    return item.attachment.kind === 'image' || item.attachment.mime_type.startsWith('image/')
  }
  return false
}
