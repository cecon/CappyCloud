import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Code,
  Group,
  Loader,
  SegmentedControl,
  Select,
  Stack,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core'
import {
  IconAlertTriangle,
  IconArrowBackUp,
  IconBoxMultiple,
  IconClick,
  IconFileCode,
  IconFocusCentered,
  IconFunction,
  IconHandGrab,
  IconRefresh,
  IconRoute,
  IconSearch,
  IconTopologyStar3,
  IconZoomIn,
  IconZoomOut,
} from '@tabler/icons-react'
import { InteractiveNvlWrapper } from '@neo4j-nvl/react'
import type NVL from '@neo4j-nvl/base'
import type { Node as NvlNode, Relationship as NvlRelationship } from '@neo4j-nvl/base'
import { useSearchParams } from 'react-router-dom'
import {
  errorToUserMessage,
  fetchRepositoryGraph,
  getToken,
  type Repository,
  type RepositoryGraph,
  type RepositoryGraphEdge,
  type RepositoryGraphFile,
  type RepositoryGraphSemanticNode,
  type RepositoryGraphSymbol,
} from '../api'
import styles from './RepositoryGraphPanel.module.css'

type RepositoryGraphPanelProps = {
  repos: Repository[]
}

type ViewMode = 'flows' | 'focus' | 'structure' | 'unreferenced'
type GraphNodeKind =
  | 'repo'
  | 'folder'
  | 'file'
  | 'ui_action'
  | 'function'
  | 'method'
  | 'class'
  | 'route'
  | 'action'
  | 'call'
  | 'saga'
  | 'reducer'
  | 'data'
  | 'ignore'
  | 'reference'

type VisualNode = NvlNode & {
  id: string
  caption: string
  kind: GraphNodeKind
  path?: string
  line?: number
  symbolId?: string
  filePath?: string
  detail?: string
}

type VisualRelationship = NvlRelationship & {
  id: string
  from: string
  to: string
  type: string
}

type VisualGraph = {
  nodes: VisualNode[]
  rels: VisualRelationship[]
  fitIds: string[]
}

type SearchHit = {
  id: string
  label: string
  detail: string
  kind: 'ui_action' | 'file' | 'symbol' | 'route'
  nodeId: string
  filePath?: string
  symbolId?: string
}

type HtmlLabelOptions = {
  badge?: string
  meta?: string
  nodeId?: string
  variant?: 'button' | 'input' | 'grid' | 'screen' | 'file' | 'code' | 'language'
}

const MAX_FLOW_NODES = 72
const FLOW_DEPTH = 2

function normalize(value: string): string {
  return value.toLowerCase()
}

function compactLabel(value: string, size = 30): string {
  return value.length > size ? `${value.slice(0, size - 3)}...` : value
}

function shortPathLabel(value: string, segments = 2): string {
  const parts = value.split('/').filter(Boolean)
  if (parts.length <= segments) return value
  return parts.slice(-segments).join('/')
}

function fileTypeBadge(path: string): string {
  const name = path.toLowerCase()
  if (/(^|\/)(store|stores|redux|sagas?|reducers?|actions?|ducks?)(\/|\.|$)/i.test(path) || /\b(saga|reducer|action|duck)s?\b/i.test(name)) {
    return 'RX'
  }
  if (name.endsWith('.tsx') || name.endsWith('.jsx')) return 'React'
  if (name.endsWith('.ts')) return 'TS'
  if (name.endsWith('.js')) return 'JS'
  if (name.endsWith('.py')) return 'PY'
  if (name.endsWith('.cs')) return 'CS'
  if (name.endsWith('.css') || name.endsWith('.scss') || name.endsWith('.sass')) return 'CSS'
  if (name.endsWith('.html') || name.endsWith('.htm')) return 'HTML'
  if (name.endsWith('.glade')) return 'UI'
  if (name.endsWith('.json')) return 'JSON'
  if (name.endsWith('.md')) return 'MD'
  if (name.endsWith('.env')) return 'ENV'
  if (name.endsWith('.gitignore')) return 'GIT'
  const ext = name.split('.').pop()
  return ext && ext !== name ? ext.slice(0, 4).toUpperCase() : 'FILE'
}

function classToken(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-')
}

function uiElementVariant(symbol: RepositoryGraphSymbol): HtmlLabelOptions['variant'] {
  const source = normalize(`${symbol.element ?? ''} ${symbol.container ?? ''} ${symbol.name} ${symbol.signature}`)
  if (
    source.includes('input') ||
    source.includes('textfield') ||
    source.includes('textarea') ||
    source.includes('picker') ||
    source.includes('select') ||
    source.includes('gtkentry') ||
    source.includes('gtkcombo') ||
    source.includes('gtkspin') ||
    source.includes('gtktextview') ||
    source.includes('gtkcalendar')
  ) {
    return 'input'
  }
  if (
    source.includes('grid') ||
    source.includes('table') ||
    source.includes('flatlist') ||
    source.includes('sectionlist') ||
    source.includes('list') ||
    source.includes('gtktreeview') ||
    source.includes('gtkliststore')
  ) {
    return 'grid'
  }
  return 'button'
}

function htmlLabel(
  caption: string,
  kind: GraphNodeKind,
  selected: boolean,
  options: HtmlLabelOptions = {},
): HTMLElement | undefined {
  if (typeof document === 'undefined') return undefined
  const label = document.createElement('div')
  label.className = [
    'repoGraphNodeHtml',
    `repoGraphNodeHtml-${kind}`,
    options.variant ? `repoGraphNodeHtml-${options.variant}` : '',
    options.badge ? `repoGraphNodeHtml-badge-${classToken(options.badge)}` : '',
    selected ? 'repoGraphNodeHtml-selected' : '',
  ]
    .filter(Boolean)
    .join(' ')
  label.title = caption
  if (options.nodeId) label.dataset.nodeId = options.nodeId

  const text = document.createElement('span')
  text.className = 'repoGraphNodeHtmlText'
  text.textContent = compactLabel(caption, options.variant === 'button' ? 24 : kind === 'ui_action' || kind === 'route' ? 38 : 30)

  if (options.variant === 'button') {
    label.append(text)
    return label
  }

  const badge = document.createElement('span')
  badge.className = 'repoGraphNodeHtmlBadge'
  badge.textContent = options.badge ?? (kind === 'ui_action' ? 'UI' : kind === 'route' ? 'SCREEN' : kind === 'class' ? 'CLASS' : kind === 'method' || kind === 'function' ? 'FN' : kind.toUpperCase())

  label.append(badge, text)

  if (options.meta) {
    const meta = document.createElement('span')
    meta.className = 'repoGraphNodeHtmlMeta'
    meta.textContent = compactLabel(options.meta, 34)
    label.append(meta)
  }

  return label
}

function pathParent(value: string): string {
  const parts = value.split('/').filter(Boolean)
  return parts.slice(0, -1).join('/')
}

function folderNodeId(value: string): string {
  return `folder:${value}`
}

function symbolLabel(symbol: RepositoryGraphSymbol): string {
  if (symbol.kind === 'ui_action') return symbol.name
  if (symbol.kind === 'ignore') return symbol.name
  return symbol.container && !['Button', 'TouchableOpacity', 'Pressable'].includes(symbol.container)
    ? `${symbol.container}.${symbol.name}`
    : symbol.name
}

function symbolKindLabel(kind: string): string {
  if (kind === 'class') return 'classe'
  if (kind === 'method') return 'método'
  if (kind === 'ui_action') return 'interface'
  if (kind === 'ignore') return 'regra'
  return 'função'
}

function fallbackFiles(graph: RepositoryGraph | null): RepositoryGraphFile[] {
  if (!graph) return []
  if (graph.files?.length) return graph.files
  return graph.nodes
    .filter((node) => node.type === 'module')
    .map((node) => ({
      id: `file:${node.path}`,
      path: node.path,
      label: node.label,
      module: node.path,
      extension: '',
      line_count: 0,
      symbol_count: 0,
      imports: [],
      imported_by: [],
      import_count: node.import_count,
      imported_by_count: node.imported_by_count,
      isolated: node.isolated,
      entrypoint: false,
      unreferenced: node.isolated,
      symbols: [],
    }))
}

function nodeColor(kind: GraphNodeKind): string {
  if (kind === 'repo') return '#4f8ef7'
  if (kind === 'folder') return '#64758a'
  if (kind === 'file') return '#3ecf8e'
  if (kind === 'ui_action') return '#f5a623'
  if (kind === 'route') return '#9ed8ff'
  if (kind === 'action') return '#c58cff'
  if (kind === 'saga') return '#8d62d9'
  if (kind === 'reducer') return '#3ecf8e'
  if (kind === 'data') return '#5fd0ba'
  if (kind === 'call') return '#7a7a8a'
  if (kind === 'ignore') return '#f0b44d'
  if (kind === 'class') return '#ff7a90'
  return '#b8bc73'
}

function relationshipColor(type: string): string {
  if (type === 'renders') return '#64758a'
  if (type === 'triggers') return '#f5a623'
  if (type === 'navigates') return '#9ed8ff'
  if (type === 'dispatches') return '#c58cff'
  if (type === 'calls') return '#b8bc73'
  if (type === 'defines') return '#7a7a8a'
  if (type === 'forks') return '#b8bc73'
  if (type === 'reduces') return '#3ecf8e'
  if (type === 'selects') return '#9ed8ff'
  if (type === 'watches') return '#f5a623'
  if (type === 'queries') return '#5fd0ba'
  if (type === 'persists') return '#3ecf8e'
  if (type === 'imports') return '#4f8ef7'
  if (type === 'contains') return '#4a5666'
  return '#7a7a8a'
}

function nodeSize(kind: GraphNodeKind, selected: boolean): number {
  const base =
    kind === 'repo'
      ? 10
      : kind === 'ui_action'
        ? 7
        : kind === 'route'
          ? 7
          : kind === 'file'
            ? 6
            : kind === 'folder'
              ? 6
              : 6
  return selected ? base + 2 : base
}

function typeForSymbol(symbol: RepositoryGraphSymbol): GraphNodeKind {
  if (symbol.kind === 'ui_action') return 'ui_action'
  if (symbol.kind === 'ignore') return 'ignore'
  if (symbol.kind === 'class') return 'class'
  if (symbol.kind === 'method') return 'method'
  return 'function'
}

function typeForSemanticNode(node: RepositoryGraphSemanticNode): GraphNodeKind {
  if (node.type === 'route') return 'route'
  if (node.type === 'action') return 'action'
  if (node.type === 'call') return 'call'
  if (node.type === 'saga') return 'saga'
  if (node.type === 'reducer') return 'reducer'
  if (node.type === 'data') return 'data'
  return 'reference'
}

function scoreAction(symbol: RepositoryGraphSymbol): number {
  const label = normalize(`${symbol.name} ${symbol.file_path} ${symbol.handler ?? ''}`)
  const source = normalize(`${symbol.name} ${symbol.file_path} ${symbol.handler ?? ''} ${symbol.element ?? ''} ${symbol.signature}`)
  const isButton = source.includes('gtkbutton') || source.includes('button') || source.includes('clicked') || /\bbt[_\s-]/.test(source)
  const isGrid = source.includes('gtktreeview') || source.includes('gtkliststore') || source.includes('grid') || source.includes('row_')
  const isInput = source.includes('gtkentry') || source.includes('gtkcombo') || source.includes('changed=') || source.includes('update')
  return (
    (isButton ? 520 : 0) +
    (isGrid ? 180 : 0) -
    (isInput && !isButton ? 220 : 0) +
    (label.includes('iniciar atendimento') ? 2000 : 0) +
    (label.includes('atendimento') ? 800 : 0) +
    (label.includes('menu') ? 260 : 0) +
    (label.includes('pay') || label.includes('pagamento') ? 180 : 0) +
    (symbol.handler ? 120 : 0) -
    (['sim', 'não', 'fechar', 'cancelar'].includes(normalize(symbol.name)) ? 150 : 0)
  )
}

function isGenericUiAction(symbol: RepositoryGraphSymbol): boolean {
  const name = normalize(symbol.name).replace(/\s+/g, ' ').trim()
  return [
    '',
    'bar icon',
    'button',
    'cart footer',
    'close',
    'empty',
    'flat list',
    'item',
    'styled item',
    'top',
  ].includes(name) || name.includes('`') || name.includes(' .')
}

function relationLabel(type: string): string {
  if (type === 'renders') return 'RENDERIZA'
  if (type === 'triggers') return 'ACIONA'
  if (type === 'navigates') return 'NAVEGA'
  if (type === 'dispatches') return 'DISPATCH'
  if (type === 'calls') return 'CHAMA'
  if (type === 'defines') return 'DEFINE'
  if (type === 'forks') return 'FORK'
  if (type === 'imports') return 'IMPORTA'
  if (type === 'contains') return 'CONTÉM'
  if (type === 'reduces') return 'REDUCER'
  if (type === 'selects') return 'SELECT'
  if (type === 'watches') return 'WATCHES'
  if (type === 'queries') return 'CONSULTA'
  if (type === 'persists') return 'GRAVA'
  return type.toUpperCase()
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function edgeEndpoints(edge: RepositoryGraphEdge): [string, string] {
  return [edge.source, edge.target]
}

function collectNeighborhood(
  seeds: string[],
  edges: RepositoryGraphEdge[],
  maxDepth = FLOW_DEPTH,
  maxNodes = MAX_FLOW_NODES,
): Set<string> {
  const selected = new Set(seeds)
  const frontier = [...seeds]
  const adjacency = new Map<string, string[]>()

  for (const edge of edges) {
    const [source, target] = edgeEndpoints(edge)
    const sourceList = adjacency.get(source) ?? []
    sourceList.push(target)
    adjacency.set(source, sourceList)
    const targetList = adjacency.get(target) ?? []
    targetList.push(source)
    adjacency.set(target, targetList)
  }

  for (let depth = 0; depth < maxDepth && frontier.length > 0; depth += 1) {
    const layerSize = frontier.length
    for (let index = 0; index < layerSize; index += 1) {
      const current = frontier.shift()
      if (!current) continue
      for (const next of adjacency.get(current) ?? []) {
        if (selected.has(next)) continue
        selected.add(next)
        frontier.push(next)
        if (selected.size >= maxNodes) return selected
      }
    }
  }
  return selected
}

function buildNodeFactory({
  graph,
  filesByPath,
  symbolsById,
  semanticNodesById,
  selectedNodeId,
}: {
  graph: RepositoryGraph | null
  filesByPath: Map<string, RepositoryGraphFile>
  symbolsById: Map<string, RepositoryGraphSymbol>
  semanticNodesById: Map<string, RepositoryGraphSemanticNode>
  selectedNodeId: string | null
}) {
  return (id: string): VisualNode | null => {
    if (graph && id === `repo:${graph.slug}`) {
      const selected = id === selectedNodeId
      return {
        id,
        caption: graph.slug,
        kind: 'repo',
        html: htmlLabel(graph.slug, 'repo', selected, { badge: 'REPO', nodeId: id, variant: 'screen' }),
        color: nodeColor('repo'),
        size: nodeSize('repo', selected),
        captionSize: 12,
        captionAlign: 'center',
        selected,
      }
    }

    if (id.startsWith('file:')) {
      const filePath = id.slice('file:'.length)
      const file = filesByPath.get(filePath)
      if (!file) return null
      const selected = id === selectedNodeId
      const caption = shortPathLabel(file.path, selected ? 3 : 2)
      return {
        id,
        caption,
        kind: file.path === '.gitignore' ? 'ignore' : 'file',
        path: file.path,
        filePath: file.path,
        detail: `${file.symbol_count} símbolos · ${file.imported_by_count} entradas`,
        html:
          selected || file.entrypoint || file.path === '.gitignore'
            ? htmlLabel(caption, file.path === '.gitignore' ? 'ignore' : 'file', selected, {
                badge: fileTypeBadge(file.path),
                meta: file.path.includes('/') ? pathParent(file.path) : undefined,
                nodeId: id,
                variant: 'language',
              })
            : undefined,
        color: nodeColor(file.path === '.gitignore' ? 'ignore' : 'file'),
        size: nodeSize('file', selected),
        captionSize: selected ? 11 : 9,
        captionAlign: 'bottom',
        selected,
      }
    }

    if (id.startsWith('folder:')) {
      const folder = id.slice('folder:'.length)
      const selected = id === selectedNodeId
      const caption = shortPathLabel(folder, selected ? 3 : 2)
      return {
        id,
        caption,
        kind: 'folder',
        path: folder,
        detail: 'pasta',
        html: selected ? htmlLabel(caption, 'folder', selected, { badge: 'DIR', nodeId: id, variant: 'file' }) : undefined,
        color: nodeColor('folder'),
        size: nodeSize('folder', selected),
        captionSize: selected ? 11 : 9,
        captionAlign: 'bottom',
        selected,
      }
    }

    const symbol = symbolsById.get(id)
    if (symbol) {
      const kind = typeForSymbol(symbol)
      const selected = id === selectedNodeId
      const caption = compactLabel(symbolLabel(symbol), kind === 'ui_action' ? 34 : 28)
      const variant = kind === 'ui_action' ? uiElementVariant(symbol) : 'code'
      const codeBadge = fileTypeBadge(symbol.file_path)
      return {
        id,
        caption,
        kind,
        path: symbol.file_path,
        filePath: symbol.file_path,
        line: symbol.line,
        symbolId: symbol.id,
        detail: `${symbolKindLabel(symbol.kind)} · ${symbol.file_path}:${symbol.line}`,
        html: htmlLabel(caption, kind, selected, {
          badge:
            kind === 'ui_action'
              ? variant === 'input'
                ? 'INPUT'
                : variant === 'grid'
                  ? 'GRID'
                  : 'BUTTON'
              : codeBadge,
          meta: kind === 'ui_action' ? (symbol.handler ?? symbol.element ?? symbol.container) : shortPathLabel(symbol.file_path, 1),
          nodeId: id,
          variant: kind === 'ui_action' ? variant : 'language',
        }),
        color: nodeColor(kind),
        size: nodeSize(kind, selected) + (kind === 'ui_action' ? 4 : 0),
        captionSize: kind === 'ui_action' || selected ? 12 : 9,
        captionAlign: kind === 'ui_action' || selected ? 'center' : 'bottom',
        selected,
      }
    }

      const semanticNode = semanticNodesById.get(id)
      if (semanticNode) {
        const kind = typeForSemanticNode(semanticNode)
        const selected = id === selectedNodeId
        const caption = compactLabel(semanticNode.label, 32)
        return {
          id,
          caption,
          kind,
          path: semanticNode.path,
          line: semanticNode.line,
          detail: semanticNode.detail,
          html: htmlLabel(caption, kind, selected, {
            badge:
              kind === 'route'
                ? 'SCREEN'
                : kind === 'action' || kind === 'saga' || kind === 'reducer'
                  ? 'RX'
                  : kind === 'data'
                    ? 'DB'
                    : kind === 'call'
                      ? 'CALL'
                      : 'REF',
            meta: semanticNode.path ? shortPathLabel(semanticNode.path, 2) : undefined,
            nodeId: id,
            variant: kind === 'route' ? 'screen' : kind === 'action' || kind === 'saga' || kind === 'reducer' ? 'language' : 'code',
          }),
          color: nodeColor(kind),
          size: nodeSize(kind, selected) + (kind === 'route' ? 3 : 0),
          captionSize: kind === 'route' || selected ? 12 : 9,
          captionAlign: kind === 'route' || selected ? 'center' : 'bottom',
          selected,
        }
    }

    if (id.startsWith('route:')) {
      const selected = id === selectedNodeId
      return {
        id,
        caption: id.slice('route:'.length),
        kind: 'route',
        detail: 'rota/tela',
        html: htmlLabel(id.slice('route:'.length), 'route', selected, { badge: 'SCREEN', nodeId: id, variant: 'screen' }),
        color: nodeColor('route'),
        size: nodeSize('route', selected) + 3,
        captionSize: 12,
        captionAlign: 'center',
        selected,
      }
    }

    return null
  }
}

function buildVisualGraph({
  graph,
  mode,
  query,
  selectedNodeId,
  activeFilePath,
  files,
  filesByPath,
  symbols,
  symbolsById,
  semanticNodesById,
}: {
  graph: RepositoryGraph | null
  mode: ViewMode
  query: string
  selectedNodeId: string | null
  activeFilePath: string | null
  files: RepositoryGraphFile[]
  filesByPath: Map<string, RepositoryGraphFile>
  symbols: RepositoryGraphSymbol[]
  symbolsById: Map<string, RepositoryGraphSymbol>
  semanticNodesById: Map<string, RepositoryGraphSemanticNode>
}): VisualGraph {
  if (!graph) return { nodes: [], rels: [], fitIds: [] }

  const makeNode = buildNodeFactory({ graph, filesByPath, symbolsById, semanticNodesById, selectedNodeId })
  const selectedIds = new Set<string>()
  const rels: VisualRelationship[] = []
  const addNodeId = (id: string) => {
    if (makeNode(id)) selectedIds.add(id)
  }
  const addRelationship = (edge: RepositoryGraphEdge) => {
    const [from, to] = edgeEndpoints(edge)
    if (!selectedIds.has(from) || !selectedIds.has(to)) return
    rels.push({
      id: edge.id,
      from,
      to,
      type: relationLabel(edge.type),
      caption: relationLabel(edge.type),
      color: relationshipColor(edge.type),
      width: edge.type === 'contains' || edge.type === 'renders' ? 1 : 2,
    })
  }

  if (mode === 'structure') {
    const repoId = `repo:${graph.slug}`
    addNodeId(repoId)
    const folderPaths = new Set<string>()
    const selectedFile = activeFilePath ? filesByPath.get(activeFilePath) ?? null : null
    files
      .filter((file) => file.entrypoint || file.path === '.gitignore' || !file.path.includes('/'))
      .slice(0, 16)
      .forEach((file) => {
        addNodeId(`file:${file.path}`)
        const parent = pathParent(file.path)
        if (parent) folderPaths.add(parent)
      })
    if (selectedFile) {
      addNodeId(`file:${selectedFile.path}`)
      const parts = pathParent(selectedFile.path).split('/').filter(Boolean)
      for (let depth = 1; depth <= parts.length; depth += 1) folderPaths.add(parts.slice(0, depth).join('/'))
    }
    files
      .filter((file) => file.path.includes('/'))
      .slice(0, 120)
      .forEach((file) => {
        const parent = pathParent(file.path)
        if (parent) folderPaths.add(parent.split('/')[0])
      })
    Array.from(folderPaths)
      .filter(Boolean)
      .slice(0, 40)
      .forEach((folder) => addNodeId(folderNodeId(folder)))

    const structureEdges: RepositoryGraphEdge[] = []
    selectedIds.forEach((id) => {
      if (id.startsWith('folder:')) {
        const folder = id.slice('folder:'.length)
        const parent = pathParent(folder)
        structureEdges.push({
          id: `contains:${parent || graph.slug}:${folder}`,
          source: parent ? folderNodeId(parent) : repoId,
          target: id,
          type: 'contains',
          weight: 1,
        })
      }
      if (id.startsWith('file:')) {
        const filePath = id.slice('file:'.length)
        const parent = pathParent(filePath)
        structureEdges.push({
          id: `contains:${parent || graph.slug}:${filePath}`,
          source: parent ? folderNodeId(parent) : repoId,
          target: id,
          type: 'contains',
          weight: 1,
        })
      }
    })
    structureEdges.forEach(addRelationship)
  } else if (mode === 'unreferenced') {
    files
      .filter((file) => file.unreferenced || file.isolated)
      .slice(0, MAX_FLOW_NODES)
      .forEach((file) => addNodeId(`file:${file.path}`))
  } else {
    const search = normalize(query.trim())
    const uiActions = symbols.filter((symbol) => symbol.kind === 'ui_action')
    let seeds: string[] = []

    if (mode === 'focus' && selectedNodeId) {
      seeds = [selectedNodeId]
    } else if (search) {
      const semanticMatches = Array.from(semanticNodesById.values())
        .filter((node) => normalize(`${node.label} ${node.type} ${node.detail}`).includes(search))
        .map((node) => node.id)
      const symbolMatches = symbols
        .filter((symbol) => normalize(`${symbolLabel(symbol)} ${symbol.signature} ${symbol.file_path}`).includes(search))
        .sort((a, b) => Number(b.kind === 'ui_action') - Number(a.kind === 'ui_action') || scoreAction(b) - scoreAction(a))
        .map((symbol) => symbol.id)
      const fileMatches = files
        .filter((file) => normalize(`${file.path} ${file.module}`).includes(search))
        .map((file) => `file:${file.path}`)
      seeds = [...symbolMatches, ...semanticMatches, ...fileMatches].slice(0, 18)
    } else {
      seeds = uiActions
        .filter((symbol) => !isGenericUiAction(symbol))
        .sort((a, b) => scoreAction(b) - scoreAction(a))
        .slice(0, 12)
        .map((symbol) => symbol.id)
    }

    if (selectedNodeId && !seeds.includes(selectedNodeId)) seeds.unshift(selectedNodeId)
    if (seeds.length === 0 && graph.semantic_edges?.length) seeds = graph.semantic_edges.slice(0, 12).map((edge) => edge.source)

    const neighborhood = collectNeighborhood(seeds, graph.semantic_edges ?? [], mode === 'focus' ? 3 : FLOW_DEPTH)
    neighborhood.forEach(addNodeId)
    const trimmedIds = new Set(Array.from(selectedIds).slice(0, MAX_FLOW_NODES))
    selectedIds.clear()
    trimmedIds.forEach((id) => selectedIds.add(id))
    ;(graph.semantic_edges ?? []).forEach(addRelationship)
  }

  const nodes = Array.from(selectedIds)
    .map((id) => makeNode(id))
    .filter((node): node is VisualNode => Boolean(node))

  return {
    nodes,
    rels,
    fitIds: nodes.slice(0, 60).map((node) => node.id),
  }
}

export function RepositoryGraphPanel({ repos }: RepositoryGraphPanelProps) {
  const [searchParams] = useSearchParams()
  const nvlRef = useRef<NVL | null>(null)
  const panGestureRef = useRef<{ pointerId: number; startX: number; startY: number; panX: number; panY: number } | null>(null)
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null)
  const [graph, setGraph] = useState<RepositoryGraph | null>(null)
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null)
  const [activeSymbolId, setActiveSymbolId] = useState<string | null>(null)
  const [activeSemanticNodeId, setActiveSemanticNodeId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>('flows')
  const [navigationStack, setNavigationStack] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const preferredRepoKey = useMemo(
    () => (searchParams.get('repo') ?? searchParams.get('repository') ?? searchParams.get('repo_id') ?? '').trim().toLowerCase(),
    [searchParams],
  )

  useEffect(() => {
    if (repos.length === 0) return

    const repoFromUrl = preferredRepoKey
      ? repos.find((repo) => [repo.id, repo.slug, repo.name].some((value) => value.toLowerCase() === preferredRepoKey))
      : null
    if (!repoFromUrl && selectedRepoId) return

    const nextRepo = repoFromUrl ?? repos.find((repo) => repo.sandbox_status === 'cloned') ?? repos[0]
    if (selectedRepoId !== nextRepo.id) setSelectedRepoId(nextRepo.id)
  }, [preferredRepoKey, repos, selectedRepoId])

  const selectedRepo = useMemo(() => repos.find((repo) => repo.id === selectedRepoId) ?? null, [repos, selectedRepoId])

  const loadGraph = useCallback(async () => {
    const token = getToken()
    if (!token || !selectedRepoId) return
    setLoading(true)
    setError(null)
    try {
      const nextGraph = await fetchRepositoryGraph(token, selectedRepoId)
      const uiAction =
        nextGraph.symbols
          ?.filter((symbol) => symbol.kind === 'ui_action')
          .sort((a, b) => scoreAction(b) - scoreAction(a))[0] ?? null
      const initialFile =
        (uiAction ? nextGraph.files?.find((file) => file.path === uiAction.file_path) : null) ??
        nextGraph.files?.find((file) => file.path === 'App.js') ??
        nextGraph.files?.find((file) => file.entrypoint) ??
        nextGraph.files?.[0] ??
        null
      setGraph(nextGraph)
      setActiveFilePath(initialFile?.path ?? null)
      setActiveSymbolId(uiAction?.id ?? null)
      setActiveSemanticNodeId(null)
      setViewMode('flows')
      setNavigationStack([])
    } catch (err) {
      setGraph(null)
      setError(errorToUserMessage(err))
      setActiveFilePath(null)
      setActiveSymbolId(null)
      setActiveSemanticNodeId(null)
      setNavigationStack([])
    } finally {
      setLoading(false)
    }
  }, [selectedRepoId])

  useEffect(() => {
    void loadGraph()
  }, [loadGraph])

  const allFiles = useMemo(() => fallbackFiles(graph), [graph])
  const allSymbols = useMemo(() => graph?.symbols ?? [], [graph])
  const filesByPath = useMemo(() => new Map(allFiles.map((file) => [file.path, file])), [allFiles])
  const symbolsById = useMemo(() => new Map(allSymbols.map((symbol) => [symbol.id, symbol])), [allSymbols])
  const semanticNodesById = useMemo(
    () => new Map((graph?.semantic_nodes ?? []).map((node) => [node.id, node])),
    [graph],
  )
  const selectedFile = activeFilePath ? filesByPath.get(activeFilePath) ?? null : null
  const selectedSymbol = activeSymbolId ? symbolsById.get(activeSymbolId) ?? null : null
  const selectedSemanticNode = activeSemanticNodeId ? semanticNodesById.get(activeSemanticNodeId) ?? null : null
  const selectedNodeId = activeSymbolId ?? activeSemanticNodeId ?? (selectedFile ? `file:${selectedFile.path}` : graph ? `repo:${graph.slug}` : null)

  const visualGraph = useMemo(
    () =>
      buildVisualGraph({
        graph,
        mode: viewMode,
        query,
        selectedNodeId,
        activeFilePath,
        files: allFiles,
        filesByPath,
        symbols: allSymbols,
        symbolsById,
        semanticNodesById,
      }),
    [activeFilePath, allFiles, allSymbols, filesByPath, graph, query, selectedNodeId, semanticNodesById, symbolsById, viewMode],
  )

  useEffect(() => {
    const handle = window.setTimeout(() => {
      if (visualGraph.fitIds.length) nvlRef.current?.fit(visualGraph.fitIds, { animated: true, maxZoom: 1.35 })
    }, 260)
    return () => window.clearTimeout(handle)
  }, [visualGraph.fitIds])

  const selectNode = useCallback(
    (nodeId: string, recordHistory = true) => {
      if (recordHistory && selectedNodeId && selectedNodeId !== nodeId) {
        setNavigationStack((stack) => [...stack.filter((id) => id !== selectedNodeId), selectedNodeId].slice(-12))
      }

      const symbol = symbolsById.get(nodeId)
      if (symbol) {
        setActiveSymbolId(symbol.id)
        setActiveSemanticNodeId(null)
        setActiveFilePath(symbol.file_path)
        setViewMode('focus')
        return
      }
      const semanticNode = semanticNodesById.get(nodeId)
      if (semanticNode) {
        setActiveSemanticNodeId(semanticNode.id)
        setActiveSymbolId(null)
        setActiveFilePath(semanticNode.path || null)
        setViewMode('focus')
        return
      }
      if (nodeId.startsWith('file:')) {
        setActiveFilePath(nodeId.slice('file:'.length))
        setActiveSymbolId(null)
        setActiveSemanticNodeId(null)
        setViewMode('focus')
      }

      if (graph && nodeId === `repo:${graph.slug}`) {
        setActiveFilePath(null)
        setActiveSymbolId(null)
        setActiveSemanticNodeId(null)
        setViewMode('structure')
      }
    },
    [graph, selectedNodeId, semanticNodesById, symbolsById],
  )

  const previousNodeId = navigationStack[navigationStack.length - 1] ?? null

  const goBackNode = useCallback(() => {
    if (!previousNodeId) return
    setNavigationStack((stack) => stack.slice(0, -1))
    selectNode(previousNodeId, false)
  }, [previousNodeId, selectNode])

  const zoomGraph = useCallback((factor: number) => {
    const nvl = nvlRef.current
    if (!nvl) return
    const limits = nvl.getZoomLimits()
    nvl.setZoom(clamp(nvl.getScale() * factor, limits.minZoom, limits.maxZoom))
  }, [])

  const fitGraph = useCallback(() => {
    const selectedVisible = selectedNodeId && visualGraph.nodes.some((node) => node.id === selectedNodeId)
    const ids = selectedVisible && selectedNodeId ? [selectedNodeId] : visualGraph.fitIds
    if (ids.length) nvlRef.current?.fit(ids, { animated: true, maxZoom: selectedVisible ? 1.75 : 1.2 })
  }, [selectedNodeId, visualGraph.fitIds, visualGraph.nodes])

  const startScenePan = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    if (event.target instanceof Element && event.target.closest('[aria-label="Controles do graph"]')) return
    const pan = nvlRef.current?.getPan()
    if (!pan) return
    panGestureRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      panX: pan.x,
      panY: pan.y,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }, [])

  const moveScenePan = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const gesture = panGestureRef.current
    const nvl = nvlRef.current
    if (!gesture || !nvl || gesture.pointerId !== event.pointerId || event.buttons !== 1) return
    const zoom = nvl.getScale() || 1
    const dx = ((event.clientX - gesture.startX) / zoom) * window.devicePixelRatio
    const dy = ((event.clientY - gesture.startY) / zoom) * window.devicePixelRatio
    nvl.setPan(gesture.panX - dx, gesture.panY - dy)
    event.preventDefault()
  }, [])

  const stopScenePan = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (panGestureRef.current?.pointerId === event.pointerId) {
      panGestureRef.current = null
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }, [])

  const selectHtmlGraphNode = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>('.repoGraphNodeHtml[data-node-id]') : null
      const nodeId = target?.dataset.nodeId
      if (nodeId) selectNode(nodeId)
    },
    [selectNode],
  )

  const searchHits = useMemo<SearchHit[]>(() => {
    const search = normalize(query.trim())
    const uiHits = allSymbols
      .filter((symbol) => symbol.kind === 'ui_action')
      .filter((symbol) => search || !isGenericUiAction(symbol))
      .filter((symbol) => !search || normalize(`${symbol.name} ${symbol.file_path} ${symbol.handler ?? ''}`).includes(search))
      .sort((a, b) => scoreAction(b) - scoreAction(a))
      .slice(0, search ? 12 : 8)
      .map((symbol) => ({
        id: `hit:ui:${symbol.id}`,
        label: symbol.name,
        detail: `${symbol.element ?? (symbol.container || 'UI')} · ${symbol.file_path}:${symbol.line}`,
        kind: 'ui_action' as const,
        nodeId: symbol.id,
        filePath: symbol.file_path,
        symbolId: symbol.id,
      }))

    const routeHits = (graph?.semantic_nodes ?? [])
      .filter((node) => node.type === 'route')
      .filter((node) => !search || normalize(`${node.label} ${node.detail}`).includes(search))
      .slice(0, search ? 8 : 4)
      .map((node) => ({
        id: `hit:route:${node.id}`,
        label: node.label,
        detail: 'rota/tela',
        kind: 'route' as const,
        nodeId: node.id,
      }))

    const fileHits = allFiles
      .filter((file) => !search || normalize(`${file.path} ${file.module}`).includes(search))
      .sort((a, b) => Number(b.entrypoint) - Number(a.entrypoint) || b.imported_by_count - a.imported_by_count)
      .slice(0, search ? 8 : 4)
      .map((file) => ({
        id: `hit:file:${file.path}`,
        label: file.path,
        detail: `${file.symbol_count} símbolos · ${file.imported_by_count} entradas`,
        kind: 'file' as const,
        nodeId: `file:${file.path}`,
        filePath: file.path,
      }))

    const symbolHits = allSymbols
      .filter((symbol) => symbol.kind !== 'ui_action')
      .filter((symbol) => search && normalize(`${symbolLabel(symbol)} ${symbol.signature} ${symbol.file_path}`).includes(search))
      .slice(0, 8)
      .map((symbol) => ({
        id: `hit:symbol:${symbol.id}`,
        label: symbolLabel(symbol),
        detail: `${symbolKindLabel(symbol.kind)} · ${symbol.file_path}:${symbol.line}`,
        kind: 'symbol' as const,
        nodeId: symbol.id,
        filePath: symbol.file_path,
        symbolId: symbol.id,
      }))

    return [...uiHits, ...routeHits, ...symbolHits, ...fileHits].slice(0, 18)
  }, [allFiles, allSymbols, graph, query])

  const visibleSelectedEdges = useMemo(() => {
    if (!selectedNodeId) return []
    const allEdges = graph?.semantic_edges ?? []
    const direct = allEdges.filter((edge) => edge.source === selectedNodeId || edge.target === selectedNodeId)
    const nextTargets = new Set(direct.map((edge) => (edge.source === selectedNodeId ? edge.target : edge.source)))
    const secondHop = allEdges.filter((edge) => nextTargets.has(edge.source) && edge.target !== selectedNodeId)
    const seen = new Set<string>()
    return [...direct, ...secondHop]
      .filter((edge) => {
        if (seen.has(edge.id)) return false
        seen.add(edge.id)
        return true
      })
      .slice(0, 18)
  }, [graph, selectedNodeId])

  const nextNodeForEdge = useCallback(
    (edge: RepositoryGraphEdge) => {
      if (selectedNodeId === edge.source) return edge.target
      if (selectedNodeId === edge.target) return edge.source
      return edge.target
    },
    [selectedNodeId],
  )

  const navigateEdge = useCallback(
    (edge: RepositoryGraphEdge) => {
      selectNode(nextNodeForEdge(edge))
    },
    [nextNodeForEdge, selectNode],
  )

  const nodeCaption = useCallback(
    (id: string) => {
      if (id.startsWith('file:')) return id.slice('file:'.length)
      const symbol = symbolsById.get(id)
      if (symbol) return symbolLabel(symbol)
      const semanticNode = semanticNodesById.get(id)
      if (semanticNode) return semanticNode.label
      return id.replace(/^route:/, '').replace(/^action:/, '').replace(/^call:/, '')
    },
    [semanticNodesById, symbolsById],
  )

  const repoOptions = repos.map((repo) => ({
    value: repo.id,
    label: `${repo.name} (${repo.sandbox_status})`,
  }))

  return (
    <section className={styles.graphShell}>
      <Group justify="space-between" align="flex-start" gap="md" className={styles.graphHeader}>
        <Stack gap={4}>
          <Group gap="xs">
            <IconTopologyStar3 size={20} />
            <Text fw={700}>Graph semântico do repositório</Text>
          </Group>
          <Text c="dimmed" size="sm">
            Interface, handlers, rotas e chamadas em uma navegação próxima do Neo4j.
          </Text>
        </Stack>
        <Group gap="xs" align="flex-end">
          <Select
            aria-label="Selecionar repositório para o grafo"
            data={repoOptions}
            value={selectedRepoId}
            onChange={setSelectedRepoId}
            w={300}
            searchable
          />
          <Tooltip label="Recarregar graph">
            <ActionIcon variant="light" color="blue" onClick={() => void loadGraph()} loading={loading} aria-label="Recarregar graph">
              <IconRefresh size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      {selectedRepo && selectedRepo.sandbox_status !== 'cloned' && (
        <Alert color="yellow" icon={<IconAlertTriangle size={16} />} mt="md">
          Sincronize o repositório antes de montar o graph. Estado atual: {selectedRepo.sandbox_status}.
        </Alert>
      )}

      {error && (
        <Alert color="red" mt="md" title="Não foi possível carregar o graph">
          {error}
        </Alert>
      )}

      <div className={styles.metrics}>
        <Badge variant="light" color="yellow">{graph?.stats.ui_actions ?? 0} ações de interface</Badge>
        <Badge variant="light" color="blue">{graph?.stats.flows ?? graph?.semantic_edges?.length ?? 0} relações de fluxo</Badge>
        <Badge variant="light" color="green">{graph?.stats.symbols ?? graph?.symbols?.length ?? 0} métodos/classes/regras</Badge>
        <Badge variant="light" color="violet">{graph?.stats.links ?? 0} imports</Badge>
        <Badge variant="light" color="gray">{graph?.stats.unreferenced_files ?? graph?.stats.isolated ?? 0} sem referência local</Badge>
      </div>

      <Group gap="sm" mt="md" align="flex-end">
        <TextInput
          aria-label="Buscar nó no graph"
          leftSection={<IconSearch size={16} />}
          placeholder="Buscar botão, tela, método, arquivo... ex: Iniciar Atendimento"
          value={query}
          onChange={(event) => {
            setQuery(event.currentTarget.value)
            setViewMode('flows')
          }}
          className={styles.searchInput}
        />
        <SegmentedControl
          value={viewMode}
          onChange={(value) => setViewMode(value as ViewMode)}
          data={[
            { value: 'flows', label: 'Fluxos' },
            { value: 'focus', label: 'Foco' },
            { value: 'structure', label: 'Estrutura' },
            { value: 'unreferenced', label: 'Sem refs' },
          ]}
        />
        <Button
          variant="light"
          color="gray"
          onClick={() => {
            setQuery('')
            setViewMode('flows')
            setActiveSymbolId(null)
            setActiveSemanticNodeId(null)
            setActiveFilePath(null)
            setNavigationStack([])
          }}
        >
          Mapa geral
        </Button>
      </Group>

      <div className={styles.hitRail} aria-label="Nós encontrados">
        {searchHits.map((hit) => (
          <Button
            key={hit.id}
            variant={hit.nodeId === selectedNodeId ? 'light' : 'subtle'}
            color={hit.kind === 'ui_action' ? 'yellow' : hit.kind === 'route' ? 'cyan' : hit.kind === 'symbol' ? 'green' : 'blue'}
            size="xs"
            leftSection={
              hit.kind === 'ui_action' ? (
                <IconClick size={14} />
              ) : hit.kind === 'route' ? (
                <IconRoute size={14} />
              ) : hit.kind === 'symbol' ? (
                <IconFunction size={14} />
              ) : (
                <IconFileCode size={14} />
              )
            }
            onClick={() => selectNode(hit.nodeId)}
          >
            {compactLabel(hit.label, 32)}
          </Button>
        ))}
      </div>

      <div className={styles.graphStage}>
        <div
          className={styles.scenePanel}
          onPointerDown={startScenePan}
          onPointerMove={moveScenePan}
          onPointerUp={stopScenePan}
          onPointerCancel={stopScenePan}
          onClick={selectHtmlGraphNode}
        >
          <div className={styles.viewportControls} aria-label="Controles do graph">
            <Tooltip label="Aproximar">
              <ActionIcon variant="light" color="gray" aria-label="Aproximar graph" onClick={() => zoomGraph(1.22)}>
                <IconZoomIn size={16} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Afastar">
              <ActionIcon variant="light" color="gray" aria-label="Afastar graph" onClick={() => zoomGraph(0.82)}>
                <IconZoomOut size={16} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Centralizar">
              <ActionIcon variant="light" color="blue" aria-label="Centralizar graph" onClick={fitGraph}>
                <IconFocusCentered size={16} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Arrastar o fundo">
              <ActionIcon variant="subtle" color="gray" aria-label="Arrastar o fundo do graph">
                <IconHandGrab size={16} />
              </ActionIcon>
            </Tooltip>
          </div>
          {loading ? (
            <Group justify="center" className={styles.loadingArea}>
              <Loader size="sm" />
            </Group>
          ) : visualGraph.nodes.length > 0 ? (
            <InteractiveNvlWrapper
              ref={nvlRef}
              nodes={visualGraph.nodes}
              rels={visualGraph.rels}
              layout="d3Force"
              className={styles.nvlFrame}
              nvlOptions={{
                renderer: 'canvas',
                disableTelemetry: true,
                initialZoom: 0.58,
                minZoom: 0.04,
                maxZoom: 3.2,
                allowDynamicMinZoom: true,
                styling: {
                  defaultNodeColor: '#4f8ef7',
                  defaultRelationshipColor: '#64758a',
                  selectedBorderColor: '#f5a623',
                  selectedInnerBorderColor: '#0d0d0f',
                  dropShadowColor: '#9ed8ff',
                },
              }}
              interactionOptions={{
                selectOnClick: true,
                drawShadowOnHover: true,
                excludeNodeMargin: true,
                controlledPan: false,
                controlledZoom: false,
              }}
              mouseEventCallbacks={{
                onZoomAndPan: true,
                onNodeClick: (node) => selectNode(String(node.id)),
                onNodeDoubleClick: (node) => {
                  selectNode(String(node.id))
                  nvlRef.current?.fit([String(node.id)], { animated: true, maxZoom: 1.7 })
                },
                onCanvasDoubleClick: () => nvlRef.current?.fit(visualGraph.fitIds, { animated: true, maxZoom: 1.1 }),
              }}
            />
          ) : (
            <Group justify="center" className={styles.loadingArea}>
              <Text c="dimmed">Nenhum nó disponível para este repositório.</Text>
            </Group>
          )}
        </div>

        <aside className={styles.nodeInspector}>
          <Group gap="xs">
            <IconBoxMultiple size={16} />
            <Text fw={700} size="sm">Nó selecionado</Text>
            {previousNodeId && (
              <Tooltip label={`Voltar para ${compactLabel(nodeCaption(previousNodeId), 36)}`}>
                <ActionIcon variant="subtle" color="gray" aria-label="Voltar ao nó anterior" onClick={goBackNode} ml="auto">
                  <IconArrowBackUp size={15} />
                </ActionIcon>
              </Tooltip>
            )}
          </Group>

          <Stack gap="sm">
            {selectedSymbol ? (
              <div className={styles.inspectorBlock}>
                <Group gap={6}>
                  {selectedSymbol.kind === 'ui_action' ? <IconClick size={14} /> : <IconFunction size={14} />}
                  <Text size="sm" fw={700}>{symbolLabel(selectedSymbol)}</Text>
                  <Code>:{selectedSymbol.line}</Code>
                </Group>
                <Text size="xs" c="dimmed" mt={4}>
                  {symbolKindLabel(selectedSymbol.kind)} · {selectedSymbol.file_path}
                </Text>
                {selectedSymbol.kind === 'ui_action' && (
                  <Group gap={6} mt={8}>
                    <Badge size="xs" variant="light" color="yellow">{selectedSymbol.element ?? (selectedSymbol.container || 'UI')}</Badge>
                    {selectedSymbol.handler && <Badge size="xs" variant="light" color="green">{selectedSymbol.handler}</Badge>}
                  </Group>
                )}
                <Text size="xs" mt={8} className={styles.signature}>
                  {selectedSymbol.signature}
                </Text>
              </div>
            ) : selectedSemanticNode ? (
              <div className={styles.inspectorBlock}>
                <Group gap={6}>
                  <IconRoute size={14} />
                  <Text size="sm" fw={700}>{selectedSemanticNode.label}</Text>
                </Group>
                <Text size="xs" c="dimmed" mt={4}>{selectedSemanticNode.detail || selectedSemanticNode.type}</Text>
              </div>
            ) : selectedFile ? (
              <div className={styles.inspectorBlock}>
                <Text fw={700}>{selectedFile.path}</Text>
                <Text size="xs" c="dimmed">módulo: {selectedFile.module}</Text>
                <Group gap={6} mt={8}>
                  <Badge size="xs" variant="light">{selectedFile.line_count} linhas</Badge>
                  <Badge size="xs" variant="light">{selectedFile.symbol_count} símbolos</Badge>
                  <Badge size="xs" variant="light">{selectedFile.imported_by_count} entra</Badge>
                  <Badge size="xs" variant="light">{selectedFile.import_count} sai</Badge>
                </Group>
              </div>
            ) : (
              <Text size="sm" c="dimmed">Selecione um nó no graph.</Text>
            )}

            <Stack gap={6}>
              <Text size="xs" c="dimmed" fw={700} tt="uppercase">
                Relações do foco
              </Text>
              {visibleSelectedEdges.length === 0 ? (
                <Text size="sm" c="dimmed">Sem relações semânticas neste foco.</Text>
              ) : (
                visibleSelectedEdges.map((edge) => {
                  const nextNodeId = nextNodeForEdge(edge)
                  return (
                  <button key={edge.id} className={styles.edgeRowButton} type="button" onClick={() => navigateEdge(edge)}>
                    <Badge
                      size="xs"
                      color={
                        edge.type === 'navigates' || edge.type === 'selects'
                          ? 'cyan'
                          : edge.type === 'triggers' || edge.type === 'watches'
                            ? 'yellow'
                            : edge.type === 'reduces'
                              ? 'green'
                              : edge.type === 'dispatches'
                                ? 'violet'
                                : 'gray'
                      }
                      variant="light"
                    >
                      {relationLabel(edge.type)}
                    </Badge>
                    <Stack gap={1} className={styles.edgeLabel}>
                      <Text size="xs" fw={650} truncate="end">
                        {compactLabel(nodeCaption(nextNodeId), 42)}
                      </Text>
                      <Text size="xs" c="dimmed" truncate="end">
                        {compactLabel(nodeCaption(edge.source), 20)} {'->'} {compactLabel(nodeCaption(edge.target), 20)}
                      </Text>
                    </Stack>
                  </button>
                  )
                })
              )}
            </Stack>
          </Stack>
        </aside>
      </div>
    </section>
  )
}
