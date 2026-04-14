import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import TopBar from '../components/TopBar'
import { analyzePatient } from '../api/client'

const steps = [
  'Matching patient identity across available records',
  'Retrieving discharge summary and PCP chart',
  'Extracting entities and aligning to FHIR resources',
  'Computing prioritized transition gaps',
]

export default function LoadingPage() {
  const [activeStep, setActiveStep] = useState(0)
  const [error, setError] = useState('')
  const { patientId } = useParams()
  const navigate = useNavigate()

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % steps.length)
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    let mounted = true
    const run = async () => {
      try {
        const { data } = await analyzePatient(patientId)
        if (mounted) {
          navigate(`/report/${data.session_id}`)
        }
      } catch {
        if (mounted) {
          setError('Analysis failed. Please return and try again.')
        }
      }
    }
    run()
    return () => {
      mounted = false
    }
  }, [navigate, patientId])

  const progress = useMemo(() => ((activeStep + 1) / steps.length) * 100, [activeStep])

  return (
    <main className="page loading-shell">
      <TopBar title="Analyzing Transition Integrity" subtitle="Clinical context is being synthesized in real time." />
      <section className="loading-card">
        <div className="progress-rail">
          <div className="progress-value" style={{ width: `${progress}%` }} />
        </div>
        <ul>
          {steps.map((step, idx) => (
            <li key={step} className={idx <= activeStep ? 'active' : ''}>
              <span>{idx + 1}</span>
              {step}
            </li>
          ))}
        </ul>
        {error ? <p className="error">{error}</p> : null}
      </section>
    </main>
  )
}
