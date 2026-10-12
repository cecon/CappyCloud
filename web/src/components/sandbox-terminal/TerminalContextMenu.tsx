export type TerminalMenuItem = { label: string; run: () => void }

/** Menu do botão direito sobre o terminal (copiar, colar, abrir/copiar link). */
export function TerminalContextMenu({
  x,
  y,
  items,
  onClose,
}: {
  x: number
  y: number
  items: TerminalMenuItem[]
  onClose: () => void
}) {
  return (
    <div
      role="menu"
      style={{
        position: 'absolute',
        left: x,
        top: y,
        zIndex: 5,
        display: 'grid',
        minWidth: 160,
        padding: 4,
        borderRadius: 6,
        background: 'var(--popover, #221f1b)',
        border: '1px solid var(--border, #3a352e)',
        boxShadow: '0 6px 20px rgba(0,0,0,.35)',
      }}
    >
      {items.map((item) => (
        <button
          key={item.label}
          type="button"
          role="menuitem"
          onClick={() => {
            onClose()
            item.run()
          }}
          style={{
            textAlign: 'left',
            padding: '6px 10px',
            border: 0,
            borderRadius: 4,
            background: 'transparent',
            color: 'inherit',
            cursor: 'pointer',
            font: 'inherit',
            fontSize: 13,
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
