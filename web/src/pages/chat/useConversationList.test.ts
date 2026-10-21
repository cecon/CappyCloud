import { describe, expect, it } from 'vitest'
import type { Conversation } from '../../api'
import { conversationMatchesSearch } from './useConversationList'

const conversation = {
  title: 'Rejeição 232 Barueri',
  ticket_number: '30555465',
  repos: [{ slug: 'tss', alias: 'tss', base_branch: 'main' }],
} as unknown as Conversation

describe('conversationMatchesSearch', () => {
  it('encontra pelo número do chamado', () => {
    expect(conversationMatchesSearch(conversation, '30555465')).toBe(true)
  })

  it('continua encontrando por título e repositório', () => {
    expect(conversationMatchesSearch(conversation, 'barueri')).toBe(true)
    expect(conversationMatchesSearch(conversation, 'tss')).toBe(true)
    expect(conversationMatchesSearch(conversation, '99999')).toBe(false)
  })

  it('aceita conversa sem chamado', () => {
    expect(conversationMatchesSearch({ ...conversation, ticket_number: null }, '30555465')).toBe(false)
  })
})
