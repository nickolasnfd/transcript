import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

type Action = 'summary' | 'clean' | 'action_items' | 'chat'

const TABS: { id: Action; label: string; endpoint: string; button: string }[] = [
  { id: 'summary', label: 'Resumo', endpoint: 'summary', button: 'Gerar resumo' },
  { id: 'clean', label: 'Limpeza', endpoint: 'clean', button: 'Limpar texto' },
  { id: 'action_items', label: 'Itens de ação', endpoint: 'action-items', button: 'Extrair itens' },
  { id: 'chat', label: 'Chat', endpoint: 'chat', button: 'Enviar' },
]

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  transcriptionId: number
  originalText: string
  ollamaOk: boolean
  ollamaDetail?: string
}

export function LLMPanel({ transcriptionId, originalText, ollamaOk, ollamaDetail }: Props) {
  const [tab, setTab] = useState<Action>('summary')
  const [models, setModels] = useState<string[]>([])
  const [model, setModel] = useState('')
  const [outputs, setOutputs] = useState<Record<string, string>>({})
  const [chatLog, setChatLog] = useState<ChatMessage[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const outputRef = useRef<HTMLDivElement>(null)

  // Carrega modelos do Ollama, resultados salvos e histórico de chat
  useEffect(() => {
    if (ollamaOk) {
      api.ollamaModels().then((r) => setModels(r.models)).catch(() => setModels([]))
    }
    fetch(`/api/transcriptions/${transcriptionId}/llm-results`)
      .then((r) => r.json())
      .then((r) => {
        const saved: Record<string, string> = {}
        for (const [action, data] of Object.entries<{ output: string }>(r.results ?? {})) {
          saved[action] = data.output
        }
        setOutputs(saved)
      })
      .catch(() => {})
    fetch(`/api/transcriptions/${transcriptionId}/chat`)
      .then((r) => r.json())
      .then((r) => setChatLog(r.messages ?? []))
      .catch(() => {})
  }, [transcriptionId, ollamaOk])

  useEffect(() => {
    outputRef.current?.scrollTo({ top: outputRef.current.scrollHeight })
  }, [outputs, chatLog])

  async function runAction(action: Action, endpoint: string) {
    setBusy(true)
    setError(null)
    setOutputs((o) => ({ ...o, [action]: '' }))
    try {
      await api.stream(
        `/api/transcriptions/${transcriptionId}/${endpoint}`,
        { model: model || undefined },
        (chunk) => setOutputs((o) => ({ ...o, [action]: (o[action] ?? '') + chunk })),
      )
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function sendChat() {
    const message = question.trim()
    if (!message) return
    setBusy(true)
    setError(null)
    setQuestion('')
    setChatLog((log) => [...log, { role: 'user', content: message }, { role: 'assistant', content: '' }])
    try {
      await api.stream(
        `/api/transcriptions/${transcriptionId}/chat`,
        { message, model: model || undefined },
        (chunk) =>
          setChatLog((log) => {
            const next = [...log]
            next[next.length - 1] = {
              role: 'assistant',
              content: next[next.length - 1].content + chunk,
            }
            return next
          }),
      )
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!ollamaOk) {
    return (
      <div className="card llm-panel">
        <h2>🤖 Recursos de IA</h2>
        <p className="error">
          Ollama não está acessível — os recursos de resumo, limpeza, itens de ação e chat
          estão desativados. {ollamaDetail && <small>({ollamaDetail})</small>}
        </p>
        <p className="meta">
          Inicie o Ollama (<code>ollama serve</code>) e baixe um modelo
          (<code>ollama pull llama3.1:8b</code>), depois recarregue a página.
        </p>
      </div>
    )
  }

  const current = TABS.find((t) => t.id === tab)!

  return (
    <div className="card llm-panel">
      <div className="llm-header">
        <h2>🤖 Recursos de IA</h2>
        {models.length > 0 && (
          <label className="model-select">
            Modelo
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="">padrão</option>
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? 'tab active' : 'tab'} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab !== 'chat' && (
        <>
          <button
            className="primary"
            disabled={busy}
            onClick={() => runAction(tab, current.endpoint)}
          >
            {busy ? 'Gerando…' : current.button}
          </button>

          {tab === 'clean' && outputs.clean != null ? (
            <div className="side-by-side">
              <div>
                <h3>Original</h3>
                <div className="llm-output">{originalText}</div>
              </div>
              <div>
                <h3>Texto limpo</h3>
                <div className="llm-output" ref={outputRef}>
                  {outputs.clean}
                </div>
              </div>
            </div>
          ) : (
            outputs[tab] != null && (
              <div className="llm-output" ref={outputRef}>
                {outputs[tab]}
              </div>
            )
          )}
        </>
      )}

      {tab === 'chat' && (
        <div className="chat">
          <div className="chat-log" ref={outputRef}>
            {chatLog.length === 0 && (
              <p className="meta">Faça perguntas sobre o conteúdo deste áudio.</p>
            )}
            {chatLog.map((m, i) => (
              <div key={i} className={`chat-msg ${m.role}`}>
                <strong>{m.role === 'user' ? 'Você' : 'IA'}:</strong> {m.content}
              </div>
            ))}
          </div>
          <div className="chat-input">
            <input
              type="text"
              value={question}
              placeholder="Pergunte algo sobre o áudio…"
              disabled={busy}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendChat()}
            />
            <button className="primary" disabled={busy || !question.trim()} onClick={sendChat}>
              {busy ? '…' : 'Enviar'}
            </button>
          </div>
        </div>
      )}

      {error && <p className="error">{error}</p>}
    </div>
  )
}
