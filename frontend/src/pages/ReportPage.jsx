import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import AbstractivePanel from '../components/AbstractivePanel'
import GapItem from '../components/GapItem'
import Sidebar from '../components/Sidebar'
import TopBar from '../components/TopBar'
import { exportPDF, getSession, resolveGap } from '../api/client'

const severityOrder = ['critical', 'warning', 'info']

export default function ReportPage() {
  const { sessionId } = useParams()
  const [session, setSession] = useState(null)
  const [error, setError] = useState('')

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
      if (!acc[gap.severity]) acc[gap.severity] = []
      acc[gap.severity].push(gap)
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
    const { data } = await exportPDF(sessionId)
    const blob = new Blob([data], { type: 'application/pdf' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `transitionguard_${sessionId}.pdf`
    a.click()
    window.URL.revokeObjectURL(url)
  }

  if (error) return <main className="page shell"><p className="error">{error}</p></main>
  if (!session) return <main className="page shell"><p>Loading session...</p></main>

  return (
    <main className="page report-layout">
      <TopBar
        title="Gap Prioritization Dashboard"
        subtitle={`Patient ${session.patient.name || 'Unknown'} • Session ${sessionId}`}
      />
      <div className="report-grid">
        <Sidebar gaps={session.gaps} />
        <section>
          <div className="report-actions">
            <button onClick={onExport}>Export PDF</button>
          </div>
          <AbstractivePanel sources={session.sources} />
          {severityOrder.map((severity) => (
            <section className="severity-block" key={severity}>
              <h3>{severity.toUpperCase()}</h3>
              {(grouped[severity] || []).map((gap) => (
                <GapItem key={gap.id} gap={gap} onResolve={onResolve} />
              ))}
            </section>
          ))}
        </section>
      </div>
    </main>
  )
}
