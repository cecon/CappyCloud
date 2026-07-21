'use strict'

const fs = require('fs')
const net = require('net')

const STOP_SENTINEL = '/tmp/cappycloud-openclaude-stopped'
const GRPC_PORT = parseInt(process.env.GRPC_PORT || '50051', 10)
const GRPC_HEALTH_TIMEOUT_MS = parseInt(process.env.GRPC_HEALTH_TIMEOUT_MS || '750', 10)

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

function isGrpcPortOpen(timeoutMs = GRPC_HEALTH_TIMEOUT_MS) {
  if (isStopped()) return Promise.resolve(false)
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: '127.0.0.1', port: GRPC_PORT })
    let settled = false
    const finish = (value) => {
      if (settled) return
      settled = true
      socket.destroy()
      resolve(value)
    }
    socket.setTimeout(timeoutMs)
    socket.once('connect', () => finish(true))
    socket.once('timeout', () => finish(false))
    socket.once('error', () => finish(false))
  })
}

async function openClaudeStatus() {
  if (isStopped()) return 'stopped'
  return (await isGrpcPortOpen()) ? 'running' : 'unhealthy'
}

async function tryHandle(req, res, { json, clearActiveSessions }) {
  const pathname = (req.url || '').split('?')[0]
  if (req.method === 'GET' && pathname === '/runtime/status') {
    json(res, 200, { openclaude: await openClaudeStatus(), grpc_port: GRPC_PORT })
    return true
  }
  if (req.method === 'POST' && pathname === '/runtime/stop-openclaude') {
    fs.writeFileSync(STOP_SENTINEL, '1', 'utf8')
    if (typeof clearActiveSessions === 'function') clearActiveSessions()
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

module.exports = { STOP_SENTINEL, isStopped, isGrpcPortOpen, openClaudeStatus, tryHandle }
