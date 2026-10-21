export type FormState = {
  id: string | null
  name: string
  description: string
  content: string
  enabled: boolean
  sandbox_ids: string[]
}

export const EMPTY_FORM: FormState = {
  id: null,
  name: '',
  description: '',
  content: '',
  enabled: true,
  sandbox_ids: [],
}
