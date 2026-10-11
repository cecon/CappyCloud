'use strict'
// Uso por turno do runtime Claude CLI: tokens (com a quebra de cache), modelo
// principal e janelas da assinatura. Funções puras, sem I/O.

/**
 * Modelo principal do turno. O Claude Code também gasta tokens com modelos
 * auxiliares (ex.: Haiku para tarefas internas), então a primeira chave de
 * `modelUsage` nem sempre é o modelo que respondeu.
 */
function mainModel(modelUsage, initModel) {
  const usage = modelUsage || {}
  if (initModel && usage[initModel]) return initModel
  let best = ''
  let bestOutput = -1
  for (const [model, item] of Object.entries(usage)) {
    if ((item.outputTokens || 0) > bestOutput) {
      best = model
      bestOutput = item.outputTokens || 0
    }
  }
  return best || initModel
}

/** Fração (0-1, como o Claude Code manda) ou percentual → percentual com 1 casa. */
function toPercent(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  const pct = value <= 1 ? value * 100 : value
  return Math.round(Math.min(Math.max(pct, 0), 100) * 10) / 10
}

/**
 * Uso da assinatura (`claude login`) a partir do `rate_limit_event`: quanto
 * das janelas de 5 horas e 7 dias já foi usado e quando cada uma renova.
 */
function planUsageFrom(info) {
  if (!info || typeof info !== 'object') return null
  const windows = { ...(info.unifiedWindows || {}) }
  if (info.rateLimitType && !windows[info.rateLimitType]) {
    windows[info.rateLimitType] = { utilization: info.utilization, resetsAt: info.resetsAt }
  }
  const usage = { status: info.status || null }
  for (const name of ['five_hour', 'seven_day']) {
    const window = windows[name]
    if (!window) continue
    const resetsAt = Number(window.resetsAt)
    usage[name] = {
      used_pct: toPercent(window.utilization),
      resets_at: Number.isFinite(resetsAt) && resetsAt > 0 ? new Date(resetsAt * 1000).toISOString() : null,
    }
  }
  return usage.five_hour || usage.seven_day ? usage : null
}

/**
 * `promptTokens` soma entrada + leitura + gravação de cache (cada uma tem preço
 * diferente); `cacheReadTokens` e `cacheWriteTokens` são as parcelas de cache.
 */
function sumUsage(modelUsage) {
  let promptTokens = 0
  let completionTokens = 0
  let cacheReadTokens = 0
  let cacheWriteTokens = 0
  for (const usage of Object.values(modelUsage || {})) {
    cacheReadTokens += usage.cacheReadInputTokens || 0
    cacheWriteTokens += usage.cacheCreationInputTokens || 0
    promptTokens += (usage.inputTokens || 0) + (usage.cacheReadInputTokens || 0) +
      (usage.cacheCreationInputTokens || 0)
    completionTokens += usage.outputTokens || 0
  }
  return { promptTokens, completionTokens, cacheReadTokens, cacheWriteTokens }
}

/**
 * Cache do turno. Totais gravados antes desta quebra existir não têm as chaves
 * de cache: o delta daria o acumulado da sessão, então o turno fica sem quebra.
 */
function cacheDelta(read, write, before) {
  if (Object.keys(before).length && !('cache_read_tokens' in before)) return {}
  return {
    cache_read_tokens: delta(read, before.cache_read_tokens),
    cache_write_tokens: delta(write, before.cache_write_tokens),
  }
}

/** Diferença do acumulado; se o total caiu (sessão nova), o próprio total. */
function delta(current, previous) {
  const before = Number(previous) || 0
  return current >= before ? current - before : current
}

module.exports = { cacheDelta, delta, mainModel, planUsageFrom, sumUsage }
