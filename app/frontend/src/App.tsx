import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { ProgressCard } from './components/ProgressCard'
import { TranscriptView } from './components/TranscriptView'
import { UploadCard } from './components/UploadCard'
import type { HealthStatus, JobCreated, TranscriptionDetail } from './types'
import './App.css'

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [job, setJob] = useState<JobCreated | null>(null)
  const [transcript, setTranscript] = useState<TranscriptionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  const openTranscription = useCallback((id: number) => {
    api
      .get(id)
      .then((t) => {
        setTranscript(t)
        setJob(null)
      })
      .catch((e) => setError((e as Error).message))
  }, [])

  return (
    <div className="app">
      <header>
        <h1>🎙 Transcritor Local</h1>
        <p className="subtitle">Whisper + Ollama — 100% na sua máquina</p>
        {health && (
          <div className="health">
            <span className={health.ffmpeg.ok ? 'ok' : 'bad'}>
              ffmpeg {health.ffmpeg.ok ? '✓' : '✗'}
            </span>
            <span className={health.ollama.ok ? 'ok' : 'bad'}>
              Ollama {health.ollama.ok ? '✓' : '✗ (recursos de IA desativados)'}
            </span>
            <span className="ok">{health.gpu.cuda ? 'GPU ✓' : 'CPU'}</span>
          </div>
        )}
      </header>

      <main>
        <UploadCard
          defaultModel={health?.whisper_model ?? 'turbo'}
          onJobCreated={(j) => {
            setTranscript(null)
            setError(null)
            setJob(j)
          }}
        />

        {job && <ProgressCard job={job} onDone={openTranscription} />}
        {error && <p className="error">{error}</p>}
        {transcript && <TranscriptView transcript={transcript} />}
      </main>
    </div>
  )
}
