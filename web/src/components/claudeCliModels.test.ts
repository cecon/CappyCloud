import { describe, expect, it } from 'vitest'
import { CLAUDE_CLI_MODELS, claudeCliModelFor, isClaudeCliModel, planUsageBadge, usesClaudeCli } from './claudeCliModels'

describe('modelos do Claude CLI', () => {
  it('lista Opus, Sonnet e Haiku', () => {
    expect(CLAUDE_CLI_MODELS.map((model) => model.model_id)).toEqual([
      'claude-cli/opus',
      'claude-cli/sonnet',
      'claude-cli/haiku',
    ])
    expect(isClaudeCliModel('claude-cli/opus')).toBe(true)
    expect(isClaudeCliModel('anthropic/claude-opus-4.7')).toBe(false)
  })

  it('converte o modelo escolhido como o sandbox faz', () => {
    expect(claudeCliModelFor('claude-cli/haiku')).toBe('claude-cli/haiku')
    expect(claudeCliModelFor('anthropic/claude-opus-4.7')).toBe('claude-cli/opus')
    expect(claudeCliModelFor('gpt-5.4')).toBe('claude-cli/sonnet')
    expect(claudeCliModelFor('')).toBe('claude-cli/sonnet')
  })

  it('só vale para o runtime Claude CLI', () => {
    expect(usesClaudeCli('claude_cli')).toBe(true)
    expect(usesClaudeCli('openclaude')).toBe(false)
    expect(usesClaudeCli(undefined)).toBe(false)
  })
})

describe('selo de uso da assinatura', () => {
  it('mostra o que sobra da janela de 5h e detalha na dica', () => {
    const badge = planUsageBadge({
      status: 'allowed',
      five_hour: { used_pct: 12, resets_at: '2026-09-24T14:30:00.000Z' },
      seven_day: { used_pct: 7, resets_at: '2026-10-01T00:00:00.000Z' },
    })
    expect(badge?.label).toBe('5h: 88% livre')
    expect(badge?.title).toMatch(/^Janela de 5h: 12% usado, renova às \d{2}:\d{2}\. Semana: 7% usado, renova em \d{2}\/\d{2} às \d{2}:\d{2}\.$/)
    expect(badge?.low).toBe(false)
  })

  it('avisa quando sobra pouco e some sem dados', () => {
    expect(planUsageBadge({ five_hour: { used_pct: 85, resets_at: null } })).toEqual({
      label: '5h: 15% livre',
      title: 'Janela de 5h: 85% usado.',
      low: true,
    })
    expect(planUsageBadge(null)).toBeNull()
    expect(planUsageBadge({ five_hour: { used_pct: null, resets_at: null } })).toBeNull()
  })
})
