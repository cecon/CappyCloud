import { describe, expect, it } from 'vitest'

import { navigationItems, routeTitles } from './navigation'

describe('authenticated navigation coverage', () => {
  it('does not expose upstream OpenClaude branding or terminal-only features', () => {
    const visibleCopy = [
      ...navigationItems.flatMap((item) => [item.label, item.description, item.to]),
      ...Object.values(routeTitles).flatMap((item) => [item.title, item.subtitle]),
    ].join(' ')

    expect(visibleCopy).not.toMatch(/openclaude/i)
    expect(visibleCopy).not.toMatch(/buddy/i)
    expect(visibleCopy).not.toMatch(/terminal/i)
  })
})
