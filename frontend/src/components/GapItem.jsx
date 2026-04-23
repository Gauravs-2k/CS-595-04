export default function GapItem({ gap, onResolve }) {
  const resolved = Boolean(gap.resolved)
  return (
    <article className={`gap-item severity-${gap.severity}${resolved ? ' gap-resolved' : ''}`}>
      <div className="gap-main">
        <h4>{gap.title}</h4>
        <p>{gap.description}</p>
        <small>
          Source line {gap.source_line || '-'} | {gap.standard_system || 'N/A'} {gap.standard_code || ''}
        </small>
      </div>
      <div className="gap-actions">
        <p>{gap.suggested_action}</p>
        <label>
          <input
            type="checkbox"
            checked={resolved}
            onChange={() => onResolve(gap.id)}
            disabled={resolved}
            aria-label={`Mark "${gap.title}" as resolved`}
          />
          {resolved ? 'Reviewed' : 'Mark resolved'}
        </label>
      </div>
    </article>
  )
}
