'use strict'
// Subagentes do Claude Code (ferramenta Agent/Task) viram eventos `subagent_group`
// — o mesmo formato que o openclaude manda —, para o chat mostrar um cartão por
// subagente em vez de misturar as ferramentas dele com as do agente principal.

const SUBAGENT_TOOLS = new Set(['Agent', 'Task'])
const DETAIL_LIMIT = 140

function short(text) {
  const oneLine = String(text || '').replace(/\s+/g, ' ').trim()
  return oneLine.length > DETAIL_LIMIT ? `${oneLine.slice(0, DETAIL_LIMIT - 1)}…` : oneLine
}

function toolDetail(input) {
  const value = input || {}
  return short(value.description || value.command || value.file_path || value.pattern || value.path || value.url || '')
}

function createSubagentTracker() {
  const groups = new Map()

  function event(id) {
    const group = groups.get(id)
    return {
      type: 'subagent_group',
      parent_turn_id: id,
      label: group.label,
      collapsible: true,
      activities: [group.self, ...group.tools.values()],
    }
  }

  function ensure(id, description = '') {
    if (!groups.has(id)) {
      const name = short(description) || 'Subagente'
      groups.set(id, {
        label: `Subagente · ${name}`,
        self: { id, name, state: 'loading', detail: 'Iniciando' },
        tools: new Map(),
      })
    }
    return groups.get(id)
  }

  return {
    isSubagentTool: (name) => SUBAGENT_TOOLS.has(name),

    /** Agente principal chamou Agent/Task. */
    start(block) {
      const input = block.input || {}
      ensure(block.id, input.description || input.subagent_type || '')
      return event(block.id)
    },

    /** Ferramenta chamada dentro do subagente `parentId`. */
    toolStarted(parentId, block) {
      const group = ensure(parentId)
      group.self.state = 'tool-running'
      group.self.detail = `${block.name} em andamento`
      group.tools.set(block.id, { id: block.id, name: block.name, state: 'tool-running', detail: toolDetail(block.input) })
      return event(parentId)
    },

    /** Resultado de ferramenta dentro do subagente `parentId`. */
    toolFinished(parentId, block) {
      const group = ensure(parentId)
      const tool = group.tools.get(block.tool_use_id)
      if (tool) tool.state = block.is_error === true ? 'failed' : 'done'
      group.self.state = 'streaming'
      group.self.detail = 'Analisando'
      return event(parentId)
    },

    /** O agente principal recebeu o resultado do subagente: encerra o cartão. */
    finish(id, isError) {
      const group = groups.get(id)
      if (!group) return null
      group.self.state = isError ? 'failed' : 'done'
      group.self.detail = isError ? 'Falhou' : 'Concluído'
      for (const tool of group.tools.values()) {
        if (tool.state === 'tool-running') tool.state = isError ? 'canceled' : 'done'
      }
      return event(id)
    },
  }
}

module.exports = { createSubagentTracker }
