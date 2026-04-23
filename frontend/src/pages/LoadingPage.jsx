import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import TopBar from '../components/TopBar'
import { analyzePatient } from '../api/client'

const STEPS = [
  { label: 'Retrieving patient history from records network', doneAfter: 3 },
  { label: 'Processing uploaded handoff document', doneAfter: 15 },
  { label: 'Extracting clinical entities via NLP', doneAfter: 45 },
  { label: 'Computing prioritized transition gaps', doneAfter: Infinity },
]

export default function LoadingPage() {
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState('')
  const { patientId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const startRef = useRef(Date.now())

  const handoffText = location.state?.handoffText || null
  const handoffFile = location.state?.handoffFile || null

  // If no handoff data (e.g. page refresh), redirect back to upload
  useEffect(() => {
    if (!handoffText && !handoffFile) {
      navigate(`/upload/${patientId}`, { replace: true })
    }
  }, [handoffText, handoffFile, patientId, navigate])

  // Tick elapsed seconds
  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 500)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (!handoffText && !handoffFile) return
    let mounted = true
    analyzePatient(patientId, { handoffText, handoffFile })
      .then(({ data }) => { if (mounted) navigate(`/report/${data.session_id}`) })
      .catch(() => { if (mounted) setError('Analysis failed. Please go back and try again.') })
    return () => { mounted = false }
  }, [navigate, patientId, handoffText, handoffFile])

  const activeStep = STEPS.reduce((acc, s, i) => (elapsed >= s.doneAfter ? i + 1 : acc), 0)
  const progress = Math.min(95, ((activeStep) / STEPS.length) * 100 + (elapsed % 10) * 0.5)

  const waitingMsg = elapsed > 15
    ? `Processing… ${elapsed}s`
    : null

  return (
    <main className="page loading-shell">
      <TopBar title="Analyzing Transition Integrity" subtitle="Clinical context is being synthesized in real time." />
      <section className="loading-card">
        <div className="progress-rail">
          <div className="progress-value" style={{ width: `${progress}%` }} />
        </div>
        <ul>
          {STEPS.map((step, idx) => {
            const done = idx < activeStep
            const active = idx === activeStep
            return (
              <li key={step.label} className={done ? 'done' : active ? 'active' : ''}>
                <span className="step-icon">{done ? '\u2713' : idx + 1}</span>
                {step.label}
                {active && waitingMsg ? <span className="step-wait">{waitingMsg}</span> : null}
              </li>
            )
          })}
        </ul>
        {error ? (
          <>
            <p className="error">{error}</p>
            <button onClick={() => navigate(`/upload/${patientId}`)} style={{ marginTop: 12 }}>Back to Upload</button>
          </>
        ) : null}
      </section>
    </main>
  )
}
