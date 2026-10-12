import type { UserRole } from '../../api'

export type CreateFormState = {
  email: string
  password: string
  role: UserRole
  mustChangePassword: boolean
}

export const EMPTY_FORM: CreateFormState = {
  email: '',
  password: '',
  role: 'user',
  mustChangePassword: true,
}
