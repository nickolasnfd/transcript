import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { JobCreated } from '../types'

const MODELS = ['tiny', 'base', 'small', 'medium', 'large', 'turbo']
const LANGUAGES: [string, string][] = [
  ['', 'Detectar automaticamente'],
  ['pt', 'Português'],
  ['en', 'Inglês'],
  ['es', 'Espanhol'],
  ['fr', 'Francês'],
  ['de', 'Alemão'],
  ['it', 'Italiano'],
  ['ja', 'Japonês'],
  ['zh', 'Chinês'],
]

interface Props {
  defaultModel: string
  onJobCreated: (job: JobCreated) => void
}

export function UploadCard({ defaultModel, onJobCreated }: Props) {
  const [model, setModel] = useState(defaultModel)
  const [language, setLanguage] = useState('')
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recording, setRecording] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])

  // O default vem do /api/health (assíncrono); sincroniza quando chegar
  useEffect(() => setModel(defaultModel), [defaultModel])

  // Permite um modelo custom vindo do .env (ex.: caminho de checkpoint .pt)
  const modelOptions = MODELS.includes(defaultModel)
    ? MODELS
    : [defaultModel, ...MODELS]

  async function send(file: File) {
    setBusy(true)
    setError(null)
    try {
      onJobCreated(await api.upload(file, model, language || undefined))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function onDrop(ev: React.DragEvent) {
    ev.preventDefault()
    setDragging(false)
    const file = ev.dataTransfer.files[0]
    if (file) void send(file)
  }

  async function toggleRecording() {
    if (recording) {
      recorder.current?.stop()
      return
    }
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      chunks.current = []
      rec.ondataavailable = (e) => chunks.current.push(e.data)
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        setRecording(false)
        const blob = new Blob(chunks.current, { type: rec.mimeType })
        const ext = rec.mimeType.includes('ogg') ? 'ogg' : 'webm'
        void send(new File([blob], `gravacao-${Date.now()}.${ext}`))
      }
      recorder.current = rec
      rec.start()
      setRecording(true)
    } catch {
      setError('Não foi possível acessar o microfone.')
    }
  }

  return (
    <div className="card">
      <h2>Nova transcrição</h2>

      <div className="selectors">
        <label>
          Modelo Whisper
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {modelOptions.map((m) => (
              <option key={m} value={m}>
                {MODELS.includes(m) ? m : 'padrão (.env)'}
              </option>
            ))}
          </select>
        </label>
        <label>
          Idioma
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            {LANGUAGES.map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div
        className={`dropzone ${dragging ? 'dragging' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => fileInput.current?.click()}
      >
        {busy
          ? 'Enviando…'
          : 'Arraste um arquivo de áudio aqui ou clique para escolher (mp3, wav, m4a, flac, ogg, mp4)'}
        <input
          ref={fileInput}
          type="file"
          accept=".mp3,.wav,.m4a,.flac,.ogg,.mp4,.webm,audio/*"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void send(file)
            e.target.value = ''
          }}
        />
      </div>

      <button className={`record ${recording ? 'recording' : ''}`} onClick={toggleRecording}>
        {recording ? '⏹ Parar e transcrever' : '🎙 Gravar do microfone'}
      </button>

      {error && <p className="error">{error}</p>}
    </div>
  )
}
