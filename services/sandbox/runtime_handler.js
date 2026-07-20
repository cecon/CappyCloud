'use strict'

const fs = require('fs')

const STOP_SENTINEL = '/tmp/cappycloud-openclaude-stopped'

function stopOpenClaude() {
  try {
    process.kill(1, 'SIGTERM')
  } catch (err) {
    console.error('[runtime_handler] failed to signal openclaude:', err)
  }
}

function isStopped() {
  return fs.existsSync(STOP_SENTINEL)
}

async function tryHandle(req, res, { json }) {
  const pathname = (req.url || '').split('?')[0]
  if (req.method === 'GET' && pathname === '/runtime/status') {
    json(res, 200, { openclaude: isStopped() ? 'stopped' : 'running' })
    return true
  }
  if (req.method === 'POST' && pathname === '/runtime/stop-openclaude') {
    fs.writeFileSync(STOP_SENTINEL, '1', 'utf8')
    json(res, 202, { stopping: true })
    setTimeout(stopOpenClaude, 100)
    return true
  }
  if (req.method !== 'POST' || pathname !== '/runtime/restart-openclaude') {
    return false
  }

  fs.rmSync(STOP_SENTINEL, { force: true })
  json(res, 202, { restarting: true })
  setTimeout(stopOpenClaude, 100)
  return true
}

module.exports = { STOP_SENTINEL, isStopped, tryHandle }
