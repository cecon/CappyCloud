import { describe, expect, it } from 'vitest'

import type { AiModel } from '../../api'
import { findModel } from './modelKey'

const row = (id: string, modelId: string, isDefault = false) =>
  ({ id, model_id: modelId, display_name: id, is_default: { text: isDefault } }) as AiModel

describe('findModel', () => {
  const models = [row('azure', 'claude-opus-5-5'), row('lynn', 'claude-opus-5-5', true), row('gpt', 'gpt-5.4')]

  it('finds the catalog row by id', () => {
    expect(findModel(models, 'azure')?.id).toBe('azure')
  })

  it('maps an old saved model name to the default row, then the first one', () => {
    expect(findModel(models, 'claude-opus-5-5')?.id).toBe('lynn')
    expect(findModel(models, 'gpt-5.4')?.id).toBe('gpt')
  })

  it('returns nothing for unknown or empty keys', () => {
    expect(findModel(models, 'gone')).toBeUndefined()
    expect(findModel(models, '')).toBeUndefined()
  })
})
