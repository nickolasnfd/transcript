import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { TranscriptionDetail } from '../types'

function fmtTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

const EXPORT_FORMATS = ['txt', 'srt', 'vtt', 'json']

interface Props {
  transcript: TranscriptionDetail
}

export function TranscriptView({ transcript }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const activeRef = useRef<HTMLDivElement>(null)

  const activeIndex = transcript.segments.findIndex(
    (s) => currentTime >= s.start && currentTime < s.end,
  )

  // Mantém o segmento ativo visível durante a reprodução
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [activeIndex])

  function seekTo(start: number) {
    const audio = audioRef.current
    if (!audio) return
    audio.currentTime = start
    void audio.play()
  }

  return (
    <div className="card">
      <div className="transcript-header">
        <h2>{transcript.filename}</h2>
        <div className="export-buttons">
          {EXPORT_FORMATS.map((fmt) => (
            <a key={fmt} className="button" href={api.exportUrl(transcript.id, fmt)} download>
              {fmt.toUpperCase()}
            </a>
          ))}
        </div>
      </div>

      <p className="meta">
        {transcript.language && `Idioma: ${transcript.language} · `}
        {transcript.duration != null && `Duração: ${fmtTime(transcript.duration)} · `}
        Modelo: {transcript.model}
      </p>

      <audio
        ref={audioRef}
        controls
        src={api.audioUrl(transcript.id)}
        onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
        style={{ width: '100%' }}
      />

      <div className="segments">
        {transcript.segments.map((seg, i) => (
          <div
            key={seg.id}
            ref={i === activeIndex ? activeRef : undefined}
            className={`segment ${i === activeIndex ? 'active' : ''}`}
            onClick={() => seekTo(seg.start)}
            title="Clique para ouvir este trecho"
          >
            <span className="timestamp">{fmtTime(seg.start)}</span>
            <span>{seg.text}</span>
          </div>
        ))}
        {transcript.segments.length === 0 && <p>{transcript.text}</p>}
      </div>
    </div>
  )
}
