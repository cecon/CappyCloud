import { useEffect, useState } from 'react'
import { ScrollArea, Text } from '@mantine/core'
import { fetchConversationFile, fetchConversationFiles } from '../api'
import styles from './FileExplorer.module.css'

interface FileExplorerProps {
  token: string
  conversationId: string
}

interface TreeNode {
  name: string
  path: string
  children: TreeNode[]
  isFile: boolean
}

function buildTree(files: string[]): TreeNode[] {
  const root: TreeNode = { name: '', path: '', children: [], isFile: false }

  for (const file of files) {
    const parts = file.split('/')
    let node = root
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      const path = parts.slice(0, i + 1).join('/')
      const isFile = i === parts.length - 1
      let child = node.children.find((c) => c.name === part)
      if (!child) {
        child = { name: part, path, children: [], isFile }
        node.children.push(child)
      }
      node = child
    }
  }

  // Sort: directories first, then files, both alphabetically
  function sortNode(n: TreeNode): void {
    n.children.sort((a, b) => {
      if (a.isFile !== b.isFile) return a.isFile ? 1 : -1
      return a.name.localeCompare(b.name)
    })
    n.children.forEach(sortNode)
  }
  sortNode(root)

  return root.children
}

export function FileExplorer({ token, conversationId }: FileExplorerProps) {
  const [files, setFiles] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [fileLoading, setFileLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchConversationFiles(token, conversationId)
      .then(({ files }) => setFiles(files))
      .catch((e) => setError(e instanceof Error ? e.message : 'Erro ao carregar ficheiros'))
      .finally(() => setLoading(false))
  }, [token, conversationId])

  async function openFile(path: string) {
    if (selectedPath === path) {
      setSelectedPath(null)
      setFileContent(null)
      return
    }
    setSelectedPath(path)
    setFileContent(null)
    setFileLoading(true)
    try {
      const { content } = await fetchConversationFile(token, conversationId, path)
      setFileContent(content)
    } catch (e) {
      setFileContent(`Erro: ${e instanceof Error ? e.message : 'falha ao ler ficheiro'}`)
    } finally {
      setFileLoading(false)
    }
  }

  if (loading) {
    return (
      <div className={styles.loading}>
        <Text size="xs" c="dimmed">A carregar ficheiros…</Text>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.error}>
        <Text size="xs" c="red">{error}</Text>
      </div>
    )
  }

  const tree = buildTree(files)

  return (
    <div className={styles.root}>
      {/* File tree */}
      <div className={styles.tree}>
        <div className={styles.treeHeader}>
          <Text size="xs" fw={600} c="dimmed" tt="uppercase" style={{ letterSpacing: '0.08em' }}>
            Ficheiros
          </Text>
          <Text size="xs" c="dimmed">{files.length}</Text>
        </div>
        <ScrollArea className={styles.treeScroll}>
          {tree.map((node) => (
            <TreeNodeView
              key={node.path}
              node={node}
              depth={0}
              selectedPath={selectedPath}
              onSelect={openFile}
            />
          ))}
        </ScrollArea>
      </div>

      {/* File content viewer */}
      {selectedPath && (
        <div className={styles.viewer}>
          <div className={styles.viewerHeader}>
            <code className={styles.viewerPath}>{selectedPath}</code>
            <button className={styles.viewerClose} onClick={() => { setSelectedPath(null); setFileContent(null) }}>
              ✕
            </button>
          </div>
          <ScrollArea className={styles.viewerScroll}>
            {fileLoading ? (
              <div className={styles.fileLoading}>
                <Text size="xs" c="dimmed">A carregar…</Text>
              </div>
            ) : (
              <pre className={styles.fileContent}>{fileContent}</pre>
            )}
          </ScrollArea>
        </div>
      )}
    </div>
  )
}

function TreeNodeView({
  node,
  depth,
  selectedPath,
  onSelect,
}: {
  node: TreeNode
  depth: number
  selectedPath: string | null
  onSelect: (path: string) => void
}) {
  const [open, setOpen] = useState(depth === 0)

  if (node.isFile) {
    return (
      <button
        className={`${styles.treeItem} ${selectedPath === node.path ? styles.treeItemActive : ''}`}
        style={{ paddingLeft: `${0.5 + depth * 1}rem` }}
        onClick={() => onSelect(node.path)}
      >
        <span className={styles.treeIcon}>📄</span>
        <span className={styles.treeLabel}>{node.name}</span>
      </button>
    )
  }

  return (
    <div>
      <button
        className={styles.treeDir}
        style={{ paddingLeft: `${0.5 + depth * 1}rem` }}
        onClick={() => setOpen((o) => !o)}
      >
        <span className={styles.treeChevron}>{open ? '▼' : '▶'}</span>
        <span className={styles.treeIcon}>📁</span>
        <span className={styles.treeLabel}>{node.name}</span>
      </button>
      {open && node.children.map((child) => (
        <TreeNodeView
          key={child.path}
          node={child}
          depth={depth + 1}
          selectedPath={selectedPath}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}
