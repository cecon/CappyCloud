'use strict'
// ──────────────────────────────────────────────────────────────
// POST /git-auth — reconfigura credenciais git (token atualizado no DB)
// ──────────────────────────────────────────────────────────────

const { execFile, execFileSync } = require('child_process')
const { promisify } = require('util')

const execFileAsync = promisify(execFile)

/**
 * @returns {Promise<boolean>} true se a rota foi tratada
 */
async function tryHandle(req, res, { json, readBody }) {
  const pathname = (req.url || '').split('?')[0]
  if (req.method !== 'POST' || pathname !== '/git-auth') return false
  const { provider_type, token, base_url } = await readBody(req)
  try {
    if (provider_type === 'github' && token) {
      await execFileAsync('gh', ['auth', 'login', '--with-token'], {
        input: token,
        timeout: 30_000,
      }).catch(() => {
        // gh auth login via stdin pode não estar disponível — usar git credential
        execFileSync('git', ['config', '--global', `url.https://x-token:${token}@github.com/.insteadOf`, 'https://github.com/'])
      })
    } else if (provider_type === 'azure_devops' && token) {
      process.env.AZURE_DEVOPS_EXT_PAT = token
      if (base_url) {
        execFileSync('git', ['config', '--global', `url.https://:${token}@${new URL(base_url).host}/.insteadOf`, base_url])
      }
    }
    console.log(`[session_server] git-auth updated for ${provider_type}`)
    json(res, 200, { updated: true })
  } catch (err) {
    json(res, 500, { error: err.message })
  }
  return true
}

module.exports = { tryHandle }
