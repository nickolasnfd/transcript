import type {
  HealthStatus,
  JobCreated,
  JobSnapshot,
  TranscriptionDetail,
  TranscriptionSummary,
} from './types'

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const body = await resp.json()
      detail = body.detail ?? detail
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(detail)
  }
  return resp.json() as Promise<T>
}

export const api = {
  health: () => fetch('/api/health').then((r) => json<HealthStatus>(r)),

  upload: (file: File, model?: string, language?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (model) form.append('model', model)
    if (language) form.append('language', language)
    return fetch('/api/transcriptions', { method: 'POST', body: form }).then((r) =>
      json<JobCreated>(r),
    )
  },

  list: (q?: string) =>
    fetch(`/api/transcriptions${q ? `?q=${encodeURIComponent(q)}` : ''}`).then((r) =>
      json<TranscriptionSummary[]>(r),
    ),

  get: (id: number) =>
    fetch(`/api/transcriptions/${id}`).then((r) => json<TranscriptionDetail>(r)),

  remove: (id: number) =>
    fetch(`/api/transcriptions/${id}`, { method: 'DELETE' }).then((r) => {
      if (!r.ok) throw new Error(r.statusText)
    }),

  exportUrl: (id: number, format: string) =>
    `/api/transcriptions/${id}/export?format=${format}`,

  audioUrl: (id: number) => `/api/transcriptions/${id}/audio`,

  ollamaModels: () =>
    fetch('/api/ollama/models').then((r) => json<{ models: string[] }>(r)),

  watchJob: (jobId: string, onUpdate: (s: JobSnapshot) => void): WebSocket => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws/jobs/${jobId}`)
    ws.onmessage = (ev) => onUpdate(JSON.parse(ev.data))
    return ws
  },

  /** Consome um endpoint de streaming (NDJSON de tokens) chamando onToken a cada pedaço. */
  stream: async (
    url: string,
    body: unknown,
    onToken: (text: string) => void,
    signal?: AbortSignal,
  ) => {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
      signal,
    })
    if (!resp.ok || !resp.body) {
      let detail = resp.statusText
      try {
        detail = (await resp.json()).detail ?? detail
      } catch {
        /* ignore */
      }
      throw new Error(detail)
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      onToken(decoder.decode(value, { stream: true }))
    }
  },
}
