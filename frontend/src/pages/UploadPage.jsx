import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import TopBar from '../components/TopBar'
import { getDemoHandoff } from '../api/client'

export default function UploadPage() {
  const { patientId } = useParams()
  const navigate = useNavigate()
  const fileRef = useRef(null)

  const [tab, setTab] = useState('paste')   // 'paste' | 'file'
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [isDemo, setIsDemo] = useState(false)
  const [loading, setLoading] = useState(true)

  // Check if this is a demo/MIMIC patient and pre-fill
  useEffect(() => {
    getDemoHandoff(patientId)
      .then(({ data }) => {
        setText(data.handoff_text)
        setIsDemo(true)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [patientId])

  const hasContent = tab === 'paste' ? text.trim().length > 0 : file !== null

  const onSubmit = (e) => {
    e.preventDefault()
    const state = tab === 'paste'
      ? { handoffText: text }
      : { handoffFile: file }
    navigate(`/loading/${patientId}`, { state })
  }

  const onDrop = (e) => {
    e.preventDefault()
    e.currentTarget.classList.remove('drag-over')
    const dropped = e.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }

  if (loading) return null

  return (
    <main className="page shell">
      <TopBar
        title="Upload Handoff Document"
        subtitle="Upload the discharge or handoff summary to compare against existing patient records."
      />

      <div className="upload-panel">
        <div className="upload-patient-info">
          <span><strong>Patient ID:</strong> {patientId}</span>
        </div>

        {isDemo && (
          <div className="demo-banner">
            Demo data loaded — this discharge summary is pre-filled from sample data. You can edit or replace it.
          </div>
        )}

        <div className="upload-tabs">
          <button
            type="button"
            className={`upload-tab ${tab === 'paste' ? 'active' : ''}`}
            onClick={() => setTab('paste')}
          >
            Paste Text
          </button>
          <button
            type="button"
            className={`upload-tab ${tab === 'file' ? 'active' : ''}`}
            onClick={() => setTab('file')}
          >
            Upload File
          </button>
        </div>

        <form onSubmit={onSubmit}>
          {tab === 'paste' ? (
            <textarea
              className="upload-textarea"
              placeholder="Paste the discharge summary or handoff document text here..."
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          ) : (
            <div
              className="upload-dropzone"
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add('drag-over') }}
              onDragLeave={(e) => e.currentTarget.classList.remove('drag-over')}
              onDrop={onDrop}
            >
              <p><strong>Drop a file here</strong> or click to browse</p>
              <p>Supports .txt and .pdf</p>
              {file && <p className="file-name">{file.name}</p>}
              <input
                ref={fileRef}
                type="file"
                accept=".txt,.pdf"
                style={{ display: 'none' }}
                onChange={(e) => setFile(e.target.files[0] || null)}
              />
            </div>
          )}

          <div className="upload-actions">
            <Link to="/" className="btn-secondary">Back to Search</Link>
            <button type="submit" disabled={!hasContent}>
              Analyze Handoff
            </button>
          </div>
        </form>
      </div>
    </main>
  )
}
