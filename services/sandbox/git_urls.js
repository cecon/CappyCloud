'use strict'
// URLs de repositório antes de pôr credencial.
//
// O Azure DevOps ainda aceita o endereço antigo https://<org>.visualstudio.com/
// (com ou sem /DefaultCollection). O token só é injetado em dev.azure.com, então
// esse formato clonava sem credencial e falhava pedindo usuário e senha.

const LEGACY_AZURE = /^https:\/\/(?:[^@/]*@)?([a-z0-9][a-z0-9-]*)\.visualstudio\.com\/(?:DefaultCollection\/)?/i

/** https://<org>.visualstudio.com/<proj>/_git/<repo> → https://dev.azure.com/<org>/<proj>/_git/<repo> */
function normalizeAzureUrl(url) {
  const value = String(url || '')
  return value.replace(LEGACY_AZURE, (_, org) => `https://dev.azure.com/${org}/`)
}

/** Tira credenciais de URLs em mensagens de erro (git costuma citar o remoto). */
function redactCredentials(text) {
  return String(text || '').replace(/(https?:\/\/)[^@\s/]+@/gi, '$1***@')
}

module.exports = { normalizeAzureUrl, redactCredentials }
