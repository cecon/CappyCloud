'use strict'
// ──────────────────────────────────────────────────────────────
// POST /task — lança sub-agente direto no OpenRouter.
// Usado pelo agente orquestrador para delegar investigações via Bash/curl
// ou pela ferramenta `delegate` do openclaude.
// Exporta `tryHandle(req, res, { json, readBody })`.
// ──────────────────────────────────────────────────────────────

const langfuse = require('./_langfuse')

async function tryHandle(req, res, { json, readBody }) {
  const url = new URL(req.url, `http://localhost`)
  if (!(req.method === 'POST' && url.pathname === '/task')) return false

  const { description, prompt, model } = await readBody(req)
  if (!prompt) return json(res, 400, { error: 'prompt is required' }), true

  const apiKey = process.env.OPENAI_API_KEY || ''
  const baseUrl = (process.env.OPENAI_BASE_URL || 'https://openrouter.ai/api/v1').replace(/\/$/, '')
  const apiModel = model || process.env.OPENAI_MODEL || 'anthropic/claude-3.5-sonnet'

  if (!apiKey) return json(res, 500, { error: 'OPENAI_API_KEY not configured' }), true

  const startTime = new Date().toISOString()
  try {
    const resp = await fetch(`${baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: apiModel,
        messages: [{ role: 'user', content: prompt }],
        max_tokens: 8192,
      }),
    })

    if (!resp.ok) {
      const text = await resp.text()
      langfuse.logGeneration({
        name: 'sandbox:delegate',
        model: apiModel,
        input: { prompt, description: description || '' },
        output: text.slice(0, 2000),
        level: 'ERROR',
        statusMessage: `HTTP ${resp.status}`,
        startTime,
        endTime: new Date().toISOString(),
        tags: ['delegate'],
      })
      return json(res, 502, { error: 'LLM API error', detail: text.slice(0, 500) }), true
    }

    const data = await resp.json()
    const result = data.choices?.[0]?.message?.content || ''
    const usage = data.usage || {}
    langfuse.logGeneration({
      name: 'sandbox:delegate',
      model: data.model || apiModel,
      input: { prompt, description: description || '' },
      output: result,
      usage: {
        input: usage.prompt_tokens || 0,
        output: usage.completion_tokens || 0,
        total: usage.total_tokens || 0,
        unit: 'TOKENS',
      },
      startTime,
      endTime: new Date().toISOString(),
      tags: ['delegate'],
    })
    console.log(`[task_handler] "${description || ''}" — ${result.length} chars`)
    return json(res, 200, { result, description: description || '' }), true
  } catch (err) {
    langfuse.logGeneration({
      name: 'sandbox:delegate',
      model: apiModel,
      input: { prompt, description: description || '' },
      level: 'ERROR',
      statusMessage: err.message,
      startTime,
      endTime: new Date().toISOString(),
      tags: ['delegate'],
    })
    return json(res, 500, { error: err.message }), true
  }
}

module.exports = { tryHandle }
