import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { HistoryCard } from './components/HistoryCard'
import { LLMPanel } from './components/LLMPanel'
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
  const [historyKey, setHistoryKey] = useState(0)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  const openTranscription = useCallback((id: number) => {
    api
      .get(id)
      .then((t) => {
        setTranscript(t)
        setJob(null)
        setHistoryKey((k) => k + 1)
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

        <HistoryCard
          refreshKey={historyKey}
          selectedId={transcript?.id ?? null}
          onOpen={openTranscription}
          onDeleted={(id) => {
            if (transcript?.id === id) setTranscript(null)
          }}
        />

        {transcript && <TranscriptView transcript={transcript} />}
        {transcript && transcript.status === 'done' && (
          <LLMPanel
            transcriptionId={transcript.id}
            originalText={transcript.text ?? ''}
            ollamaOk={health?.ollama.ok ?? false}
            ollamaDetail={health?.ollama.detail}
          />
        )}
      </main>
    </div>
  )
}
