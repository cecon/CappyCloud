import { describe, expect, it } from 'vitest'
import { knowledgeKind, knowledgeLabel, knowledgeSummary } from './knowledgeTools'

const bash = (command: string) => JSON.stringify({ command })
const GRAPH = '/repos/workspaces/loja/knowledge/graphify/graph.json'

describe('knowledgeTools', () => {
  it('reconhece consulta ao grafo e mostra a pergunta', () => {
    const input = bash(`graphify query "como o desconto é calculado" --graph ${GRAPH} --budget 1500`)
    expect(knowledgeKind('Bash', input)).toBe('graph')
    expect(knowledgeSummary('graph', input)).toBe('query: como o desconto é calculado')
    expect(knowledgeLabel('graph').name).toBe('Grafo de código')
  })

  it('reconhece busca e gravação na memória', () => {
    const search = bash(
      "curl -s -G http://127.0.0.1:8080/memory/search --data-urlencode workspace=loja --data-urlencode 'q=versão do pdv'",
    )
    const save = bash(
      `curl -s -X POST http://127.0.0.1:8080/memory/save -H 'Content-Type: application/json' -d '{"workspace":"loja","type":"fact","content":"A versão do PDV é 1.0.47","files":"pdv/package.json"}'`,
    )
    expect(knowledgeKind('Bash', search)).toBe('memory_search')
    expect(knowledgeSummary('memory_search', search)).toBe('versão do pdv')
    expect(knowledgeKind('Bash', save)).toBe('memory_save')
    expect(knowledgeSummary('memory_save', save)).toBe('A versão do PDV é 1.0.47')
    expect(knowledgeLabel('memory_save')).toEqual({ name: 'Memória · gravação', verb: 'Gravando na memória' })
  })

  it('ignora outros comandos e ferramentas', () => {
    expect(knowledgeKind('Bash', bash('graphify update /repos/pdv'))).toBeNull()
    expect(knowledgeKind('Bash', bash('rg desconto'))).toBeNull()
    expect(knowledgeKind('Read', JSON.stringify({ file_path: '/memory/save' }))).toBeNull()
    expect(knowledgeKind('Bash', 'não é json')).toBeNull()
  })
})
