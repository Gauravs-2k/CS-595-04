import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import AbstractivePanel from '../components/AbstractivePanel'
import GapItem from '../components/GapItem'
import Sidebar from '../components/Sidebar'
import TopBar from '../components/TopBar'
import { exportPDF, getSession, resolveGap, runEvaluation } from '../api/client'

const GROUPS = [
  {
    key: 'missing_from_pcp',
    label: 'In Handoff, Not in Patient Record',
    description: 'New items from the hospital that need to be added to the patient\u2019s chart.',
  },
  {
    key: 'missing_from_handoff',
    label: 'In Patient Record, Not in Handoff',
    description: 'Existing items not mentioned in the discharge summary \u2014 may have been dropped or intentionally omitted.',
  },
  {
    key: 'changed',
    label: 'Changed Between Documents',
    description: 'Medications or labs where the value differs between the two documents.',
  },
  {
    key: 'action_needed',
    label: 'Action Items',
    description: 'Referrals, follow-ups, and pending results that need to be scheduled or ordered.',
  },
]

export default function ReportPage() {
  const { sessionId } = useParams()
  const [session, setSession] = useState(null)
  const [error, setError] = useState('')
  const [exportError, setExportError] = useState('')
  const [evaluation, setEvaluation] = useState(null)
  const [evaluationError, setEvaluationError] = useState('')
  const [evaluating, setEvaluating] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await getSession(sessionId)
        setSession(data)
      } catch {
        setError('Unable to load this analysis session.')
      }
    }
    load()
  }, [sessionId])

  const grouped = useMemo(() => {
    if (!session?.gaps) return {}
    return session.gaps.reduce((acc, gap) => {
      const key = gap.category || 'action_needed'
      if (!acc[key]) acc[key] = []
      acc[key].push(gap)
      return acc
    }, {})
  }, [session])

  const onResolve = async (gapId) => {
    await resolveGap(sessionId, gapId)
    setSession((prev) => ({
      ...prev,
      gaps: prev.gaps.map((gap) => (gap.id === gapId ? { ...gap, resolved: true } : gap)),
    }))
  }

  const onExport = async () => {
    try {
      setExportError('')
      const { data } = await exportPDF(sessionId)
      const blob = new Blob([data], { type: 'application/pdf' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `transitionguard_${sessionId}.pdf`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      setExportError('Failed to generate PDF. Please try again.')
    }
  }

  const onRunEvaluation = async () => {
    try {
      setEvaluating(true)
      setEvaluationError('')
      const { data } = await runEvaluation(sessionId)
      setEvaluation(data)
    } catch {
      setEvaluationError('Failed to run evaluation for this session.')
    } finally {
      setEvaluating(false)
    }
  }

  if (error) return <main className="page shell"><p className="error">{error}</p></main>
  if (!session) return <main className="page shell"><p>Loading session...</p></main>

  return (
    <main className="page report-layout">
      <TopBar
        title="Gap Prioritization Dashboard"
        subtitle={`Patient ${session.patient.name || 'Unknown'} \u2022 Session ${sessionId}`}
      />
      <div className="report-grid">
        <Sidebar gaps={session.gaps} />
        <section>
          <div className="report-actions">
            <Link to="/" className="btn-secondary">New Search</Link>
            {session.patient?.id?.startsWith('dataset-') && (
              <button onClick={onRunEvaluation} className="btn-secondary" disabled={evaluating}>
                {evaluating ? 'Scoring...' : 'Run Scoring'}
              </button>
            )}
            <button onClick={onExport}>Export PDF</button>
            {exportError && <span className="error" style={{ fontSize: '0.85rem' }}>{exportError}</span>}
          </div>
          {session.patient?.id?.startsWith('dataset-') && (
            <section className="evaluation-panel">
              <h3>Evaluation</h3>
              <p className="group-description">Compare detected gaps against dataset ground truth.</p>
              {evaluationError && <p className="error">{evaluationError}</p>}
              {evaluation && (
                <div className="evaluation-grid">
                  <div><strong>Precision:</strong> {(evaluation.metrics.precision * 100).toFixed(1)}%</div>
                  <div><strong>Recall:</strong> {(evaluation.metrics.recall * 100).toFixed(1)}%</div>
                  <div><strong>F1:</strong> {(evaluation.metrics.f1 * 100).toFixed(1)}%</div>
                  <div><strong>TP:</strong> {evaluation.counts.true_positives}</div>
                  <div><strong>FP:</strong> {evaluation.counts.false_positives}</div>
                  <div><strong>FN:</strong> {evaluation.counts.false_negatives}</div>
                </div>
              )}
            </section>
          )}
          <AbstractivePanel sources={session.sources} />
          {session.gaps.length === 0 ? (
            <section className="empty-state">
              <h3>No care gaps detected</h3>
              <p>All transition items appear accounted for between the handoff document and patient record.</p>
            </section>
          ) : (
            GROUPS
              .filter((group) => grouped[group.key]?.length)
              .map((group) => (
                <section className="severity-block" key={group.key}>
                  <h3>{group.label}</h3>
                  <p className="group-description">{group.description}</p>
                  {grouped[group.key].map((gap) => (
                    <GapItem key={gap.id} gap={gap} onResolve={onResolve} />
                  ))}
                </section>
              ))
          )}
        </section>
      </div>
    </main>
  )
}
