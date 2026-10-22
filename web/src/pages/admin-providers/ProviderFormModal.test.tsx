import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { EMPTY_FORM, type ProviderFormState } from './form'
import { ProviderFormModal } from './ProviderFormModal'

function Harness() {
  const [form, setForm] = useState<ProviderFormState>(EMPTY_FORM)
  return (
    <>
      <ProviderFormModal
        opened
        editingProvider={null}
        form={form}
        setForm={setForm}
        saving={false}
        canSubmit
        onClose={() => {}}
        onSave={() => {}}
      />
      <output data-testid="state">{JSON.stringify(form)}</output>
    </>
  )
}

describe('ProviderFormModal', () => {
  // Antes, o valor era lido do evento dentro do updater de setForm e a tela
  // quebrava no primeiro caractere (event.currentTarget já era null).
  it('aceita digitação nos campos sem quebrar', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.type(screen.getByPlaceholderText('Azure Eduar'), 'Lynn')
    await user.type(screen.getByLabelText(/Base URL/), 'https://proxy.dta.totvs.ai/v1')
    await user.type(screen.getByLabelText(/Modelo \/ deployment/), 'gpt-5')

    const state = JSON.parse(screen.getByTestId('state').textContent ?? '{}')
    expect(state.name).toBe('Lynn')
    expect(state.base_url).toBe('https://proxy.dta.totvs.ai/v1')
    expect(state.model_id).toBe('gpt-5')
  })
})
