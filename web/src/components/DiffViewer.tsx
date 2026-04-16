import { useState } from 'react'
import { Badge, ScrollArea, Text } from '@mantine/core'
import type { ConversationDiff, DiffFile } from '../api'
import styles from './DiffViewer.module.css'

interface DiffViewerProps {
  diff: ConversationDiff
}

export function DiffViewer({ diff }: DiffViewerProps) {
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(
    () => new Set(diff.files.map((f) => f.path))
  )

  function toggleFile(path: string) {
    setExpandedFiles((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  if (diff.files.length === 0) {
    return (
      <div className={styles.empty}>
        <Text size="sm" c="dimmed">Sem alterações em relação a {diff.base_branch}</Text>
      </div>
    )
  }

  return (
    <div className={styles.root}>
      {/* Summary bar */}
      <div className={styles.summary}>
        <span className={styles.summaryLabel}>Base: <code>{diff.base_branch}</code></span>
        <span className={styles.added}>+{diff.stats.added}</span>
        <span className={styles.removed}>−{diff.stats.removed}</span>
        <span className={styles.fileCount}>{diff.files.length} {diff.files.length === 1 ? 'ficheiro' : 'ficheiros'}</span>
      </div>

      <ScrollArea className={styles.scroll}>
        {diff.files.map((file) => (
          <DiffFileBlock
            key={file.path}
            file={file}
            expanded={expandedFiles.has(file.path)}
            onToggle={() => toggleFile(file.path)}
          />
        ))}
      </ScrollArea>
    </div>
  )
}

function DiffFileBlock({
  file,
  expanded,
  onToggle,
}: {
  file: DiffFile
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <div className={styles.file}>
      <button className={styles.fileHeader} onClick={onToggle}>
        <span className={styles.fileChevron}>{expanded ? '▼' : '▶'}</span>
        <code className={styles.filePath}>{file.path}</code>
        <div className={styles.fileStats}>
          <Badge size="xs" color="green" variant="light">+{file.added}</Badge>
          <Badge size="xs" color="red" variant="light">−{file.removed}</Badge>
        </div>
      </button>

      {expanded && (
        <div className={styles.hunks}>
          {file.hunks.map((hunk, hi) => (
            <div key={hi} className={styles.hunk}>
              <div className={styles.hunkHeader}>
                @@ -{hunk.old_start} +{hunk.new_start} @@
              </div>
              {hunk.lines.map((line, li) => (
                <div
                  key={li}
                  className={`${styles.line} ${
                    line.type === 'add'
                      ? styles.lineAdd
                      : line.type === 'remove'
                      ? styles.lineRemove
                      : styles.lineContext
                  }`}
                >
                  <span className={styles.linePrefix}>
                    {line.type === 'add' ? '+' : line.type === 'remove' ? '−' : ' '}
                  </span>
                  <code className={styles.lineContent}>{line.content}</code>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
