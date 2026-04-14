export default function AbstractivePanel({ sources = [] }) {
  return (
    <section className="abstractive-panel">
      <h3>Record Retrieval Sources</h3>
      <div className="source-grid">
        {sources.map((src, idx) => (
          <div className="source-card" key={`${src.name || 'source'}-${idx}`}>
            <p><strong>{src.name || 'Unknown source'}</strong></p>
            <p>EHR: {src.ehr || 'Unknown'}</p>
            <p>Retrieved: {src.retrieved_at || 'Unknown'}</p>
            <p>Format: {src.format || 'Unknown'}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
