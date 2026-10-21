import type { UserRole } from '../../api'

export type CreateFormState = {
  email: string
  password: string
  role: UserRole
  mustChangePassword: boolean
  /** Admin de workspace: em qual dos workspaces dele a pessoa entra. */
  workspaceId: string
}

export const EMPTY_FORM: CreateFormState = {
  email: '',
  password: '',
  role: 'user',
  mustChangePassword: true,
  workspaceId: '',
}
