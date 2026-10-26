import type { AdminConversationAttachment } from '../../api'

/** Agrupa os anexos pela pergunta em que foram enviados, na ordem de upload. */
export function groupByMessage(
  attachments: AdminConversationAttachment[],
): Map<string, AdminConversationAttachment[]> {
  const grouped = new Map<string, AdminConversationAttachment[]>()
  for (const attachment of attachments) {
    if (!attachment.message_id) continue
    grouped.set(attachment.message_id, [...(grouped.get(attachment.message_id) ?? []), attachment])
  }
  return grouped
}
