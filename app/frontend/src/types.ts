export interface Segment {
  id: number
  start: number
  end: number
  text: string
}

export interface TranscriptionSummary {
  id: number
  filename: string
  created_at: string
  duration: number | null
  language: string | null
  model: string | null
  status: string
}

export interface TranscriptionDetail extends TranscriptionSummary {
  text: string | null
  segments: Segment[]
  error: string | null
}

export interface JobCreated {
  job_id: string
  transcription_id: number
}

export interface JobSnapshot {
  job_id: string
  transcription_id: number
  status: 'queued' | 'transcribing' | 'done' | 'error'
  progress: number
  error: string | null
}

export interface HealthStatus {
  ok: boolean
  ffmpeg: { ok: boolean; detail?: string }
  ollama: { ok: boolean; models: string[]; detail?: string }
  gpu: { ok: boolean; cuda: boolean; device: string; name?: string | null }
  whisper_model: string
  ollama_model: string
}
