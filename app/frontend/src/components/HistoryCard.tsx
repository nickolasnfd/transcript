import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { TranscriptionSummary } from '../types'

const STATUS_LABEL: Record<string, string> = {
  queued: 'na fila',
  transcribing: 'transcrevendo',
  done: 'concluída',
  error: 'erro',
}

function fmtDuration(seconds: number | null): string {
  if (seconds == null) return '—'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

interface Props {
  /** Muda a cada transcrição concluída para recarregar a lista */
  refreshKey: number
  selectedId: number | null
  onOpen: (id: number) => void
  onDeleted: (id: number) => void
}

export function HistoryCard({ refreshKey, selectedId, onOpen, onDeleted }: Props) {
  const [items, setItems] = useState<TranscriptionSummary[]>([])
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback((q: string) => {
    api
      .list(q || undefined)
      .then(setItems)
      .catch((e) => setError((e as Error).message))
  }, [])

  useEffect(() => {
    const t = setTimeout(() => reload(query), query ? 250 : 0)
    return () => clearTimeout(t)
  }, [query, refreshKey, reload])

  async function remove(id: number, filename: string) {
    if (!confirm(`Excluir a transcrição de "${filename}"? O áudio também será removido.`)) return
    try {
      await api.remove(id)
      setItems((list) => list.filter((i) => i.id !== id))
      onDeleted(id)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="card">
      <div className="transcript-header">
        <h2>📚 Histórico</h2>
        <input
          type="search"
          placeholder="Buscar no conteúdo…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {error && <p className="error">{error}</p>}
      {items.length === 0 && <p className="meta">{query ? 'Nada encontrado.' : 'Nenhuma transcrição ainda.'}</p>}

      <div className="history-list">
        {items.map((t) => (
          <div
            key={t.id}
            className={`history-item ${t.id === selectedId ? 'selected' : ''}`}
            onClick={() => t.status === 'done' && onOpen(t.id)}
            title={t.status === 'done' ? 'Abrir transcrição' : STATUS_LABEL[t.status]}
          >
            <div className="history-main">
              <strong>{t.filename}</strong>
              <span className="meta">
                {new Date(t.created_at + 'Z').toLocaleString('pt-BR')} · {fmtDuration(t.duration)} ·{' '}
                {t.language ?? '—'} · {t.model?.split('/').pop()}
              </span>
            </div>
            <span className={`status status-${t.status}`}>{STATUS_LABEL[t.status] ?? t.status}</span>
            <button
              className="delete"
              title="Excluir"
              onClick={(e) => {
                e.stopPropagation()
                void remove(t.id, t.filename)
              }}
            >
              🗑
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
