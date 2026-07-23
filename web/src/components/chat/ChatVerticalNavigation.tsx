import { useState } from 'react'
import styles from './ChatVerticalNavigation.module.css'
import type { ChatNavigationMarker } from './chatNavigationMarkers'

type ChatVerticalNavigationProps = {
  markers: ChatNavigationMarker[]
  activeMarkerId: string | null
  onMarkerActivate: (marker: ChatNavigationMarker) => void
}

function actorLabel(marker: ChatNavigationMarker): string {
  if (marker.actor === 'user') return 'Tu'
  if (marker.actor === 'assistant') return 'Agente'
  return marker.kind === 'decision' ? 'Decisão' : 'Resultado'
}

function markerClassName(marker: ChatNavigationMarker, active: boolean): string {
  return [
    styles.marker,
    styles[marker.kind],
    active ? styles.markerActive : '',
    marker.groupedCount ? styles.markerGrouped : '',
  ].filter(Boolean).join(' ')
}

export function ChatVerticalNavigation({
  markers,
  activeMarkerId,
  onMarkerActivate,
}: ChatVerticalNavigationProps) {
  const [previewId, setPreviewId] = useState<string | null>(null)
  if (markers.length === 0) return null

  const preview = markers.find((marker) => marker.id === previewId) ?? null

  return (
    <nav className={styles.rail} aria-label="Navegação da conversa">
      <div className={styles.track} aria-hidden />
      <div className={styles.markers}>
        {markers.map((marker) => {
          const active = marker.id === activeMarkerId
          const label = `${actorLabel(marker)}: ${marker.title}`
          return (
            <button
              key={marker.id}
              type="button"
              className={markerClassName(marker, active)}
              aria-label={`Ir para ${label}`}
              aria-current={active ? 'location' : undefined}
              title={label}
              onClick={() => onMarkerActivate(marker)}
              onMouseEnter={() => setPreviewId(marker.id)}
              onMouseLeave={() => setPreviewId((current) => (current === marker.id ? null : current))}
              onFocus={() => setPreviewId(marker.id)}
              onBlur={() => setPreviewId((current) => (current === marker.id ? null : current))}
            >
              <span className={styles.markerDot} />
            </button>
          )
        })}
      </div>
      {preview && (
        <div className={styles.preview} role="status">
          <span className={styles.previewActor}>{actorLabel(preview)}</span>
          <span className={styles.previewTitle}>{preview.title}</span>
          <span className={styles.previewText}>{preview.preview}</span>
        </div>
      )}
    </nav>
  )
}
