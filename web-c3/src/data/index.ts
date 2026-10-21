// Camada de dados compartilhada com o frontend atual (web/src) enquanto os dois
// apps convivem. Telas importam daqui, nunca do web/ direto (specs/013, R3).
export { AuthError, changePasswordRequest, fetchCurrentUser, getToken, loginRequest, setToken } from '@cappy/api';
export type { CurrentUser } from '@cappy/api';
