import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import TopBar from '../components/TopBar'
import { analyzePatient } from '../api/client'

const STEPS = [
  { label: 'Matching patient identity across available records', doneAfter: 3 },
  { label: 'Retrieving discharge summary and PCP chart', doneAfter: 30 },
  { label: 'Extracting entities and aligning to FHIR resources', doneAfter: 90 },
  { label: 'Computing prioritized transition gaps', doneAfter: Infinity },
]

export default function LoadingPage() {
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState('')
  const { patientId } = useParams()
  const navigate = useNavigate()
  const startRef = useRef(Date.now())

  // Tick elapsed seconds — stops once all steps are done
  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 500)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    let mounted = true
    analyzePatient(patientId)
      .then(({ data }) => { if (mounted) navigate(`/report/${data.session_id}`) })
      .catch(() => { if (mounted) setError('Analysis failed. Please go back and try again.') })
    return () => { mounted = false }
  }, [navigate, patientId])

  const activeStep = STEPS.reduce((acc, s, i) => (elapsed >= s.doneAfter ? i + 1 : acc), 0)
  const progress = Math.min(95, ((activeStep) / STEPS.length) * 100 + (elapsed % 10) * 0.5)

  const waitingMsg = elapsed > 15
    ? `Waiting for Abstractive Health records… ${elapsed}s`
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
                <span className="step-icon">{done ? '✓' : idx + 1}</span>
                {step.label}
                {active && waitingMsg ? <span className="step-wait">{waitingMsg}</span> : null}
              </li>
            )
          })}
        </ul>
        {error ? <p className="error">{error}</p> : null}
      </section>
    </main>
  )
}
