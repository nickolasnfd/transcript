import { useEffect, useState } from 'react'
import { api } from '../api'
import type { JobCreated, JobSnapshot } from '../types'

const LABELS: Record<string, string> = {
  queued: 'Na fila…',
  transcribing: 'Transcrevendo…',
  done: 'Concluído!',
  error: 'Erro',
}

interface Props {
  job: JobCreated
  onDone: (transcriptionId: number) => void
}

export function ProgressCard({ job, onDone }: Props) {
  const [snapshot, setSnapshot] = useState<JobSnapshot | null>(null)

  useEffect(() => {
    const ws = api.watchJob(job.job_id, (snap) => {
      setSnapshot(snap)
      if (snap.status === 'done') onDone(snap.transcription_id)
    })
    return () => ws.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.job_id])

  const status = snapshot?.status ?? 'queued'
  const progress = Math.round((snapshot?.progress ?? 0) * 100)

  return (
    <div className="card">
      <h2>Transcrição em andamento</h2>
      <p className={status === 'error' ? 'error' : ''}>
        {LABELS[status]}
        {status === 'transcribing' && ` ${progress}%`}
      </p>
      <div className="progress-track">
        <div
          className={`progress-fill ${status}`}
          style={{ width: `${status === 'done' ? 100 : progress}%` }}
        />
      </div>
      {snapshot?.error && <p className="error">{snapshot.error}</p>}
    </div>
  )
}
