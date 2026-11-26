import type { AiModel } from '../../api'

/**
 * O chat escolhe a linha do catálogo (`id`), não só o nome do modelo: o mesmo
 * `model_id` pode estar em dois providers (ex.: Opus no Azure e no proxy do
 * Lynn). A API aceita o id da linha ou o nome em `model_id`.
 */
export function findModel(models: AiModel[], key: string | null | undefined): AiModel | undefined {
  if (!key) return undefined
  // Preferência salva antes desta mudança guarda o nome: vale a default, senão a primeira.
  return (
    models.find((model) => model.id === key) ??
    models.find((model) => model.model_id === key && model.is_default?.text) ??
    models.find((model) => model.model_id === key)
  )
}
