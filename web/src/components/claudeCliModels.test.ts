import { describe, expect, it } from 'vitest'
import { CLAUDE_CLI_MODELS, claudeCliModelFor, isClaudeCliModel, usesClaudeCli } from './claudeCliModels'

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
