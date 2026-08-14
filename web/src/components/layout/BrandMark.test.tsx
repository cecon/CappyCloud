import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { BrandMark } from './BrandMark'

describe('BrandMark', () => {
  it('keeps authenticated branding free of upstream OpenClaude copy', () => {
    const { container } = render(<BrandMark />)

    expect(screen.queryByText(/openclaude/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/buddy/i)).not.toBeInTheDocument()
    expect(container.querySelector('img')).toBeInTheDocument()
  })
})
