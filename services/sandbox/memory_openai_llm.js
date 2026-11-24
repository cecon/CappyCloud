'use strict'
// Uma volta, sem ferramentas, nas APIs estilo OpenAI do provider da conversa.
// Usado pela gravação automática da memória (memory_extract.js) quando o
// provider do openclaude está no formato "chat_completions" ou "responses".
//
// A chave vai nos dois cabeçalhos: a Azure lê `api-key`; os demais (OpenRouter,
// proxies compatíveis), `Authorization`. Nunca é logada.

// Modelos com raciocínio (gpt-5.x) gastam parte do limite pensando.
const MAX_OUTPUT_TOKENS = 8000
const TIMEOUT_MS = 150000

function headers(apiKey) {
  return {
    'content-type': 'application/json',
    authorization: `Bearer ${apiKey}`,
    'api-key': apiKey,
  }
}

function endpoint(baseUrl, path) {
  return `${String(baseUrl).replace(/\/+$/, '')}/${path}`
}

/** Texto de uma resposta da API Responses (output_text ou blocos output_text). */
function responsesText(data) {
  if (typeof data.output_text === 'string' && data.output_text) return data.output_text
  return (data.output || [])
    .flatMap((item) => item.content || [])
    .filter((block) => block.type === 'output_text' && typeof block.text === 'string')
    .map((block) => block.text)
    .join('')
}

function chatText(data) {
  const content = data.choices?.[0]?.message?.content
  if (typeof content === 'string') return content
  if (Array.isArray(content)) return content.map((part) => part.text || '').join('')
  return ''
}

function requestFor(format, { system, prompt, model }) {
  if (format === 'responses') {
    return {
      path: 'responses',
      body: { model, instructions: system, input: prompt, max_output_tokens: MAX_OUTPUT_TOKENS },
      read: responsesText,
    }
  }
  return {
    path: 'chat/completions',
    body: {
      model,
      messages: [{ role: 'system', content: system }, { role: 'user', content: prompt }],
      max_tokens: MAX_OUTPUT_TOKENS,
    },
    read: chatText,
  }
}

/** Pede ao provider ({base_url, api_key, api_format}) e devolve só o texto. */
async function askOpenAiStyle({ system, prompt, model, provider }, fetchImpl = fetch) {
  const { path, body, read } = requestFor(provider.api_format, { system, prompt, model })
  const response = await fetchImpl(endpoint(provider.base_url, path), {
    method: 'POST',
    headers: headers(provider.api_key),
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.error?.message || data.error || `HTTP ${response.status}`
    throw Object.assign(new Error(`provider respondeu ${response.status}: ${String(detail).slice(0, 200)}`), {
      status: 502,
    })
  }
  return read(data)
}

module.exports = { askOpenAiStyle, chatText, requestFor, responsesText }
