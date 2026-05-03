export default function GapItem({ gap, onResolve }) {
  const resolved = Boolean(gap.resolved)
  const severityLabel = {
    critical: 'Urgent',
    warning: 'Warning',
    info: 'Info',
  }[gap.severity] || 'Info'

  return (
    <article className={`gap-item severity-${gap.severity}${resolved ? ' gap-resolved' : ''}`}>
      <div className="gap-main">
        <div className="gap-title-row">
          <span className={`gap-severity-badge badge-${gap.severity}`}>{severityLabel}</span>
        </div>
        <h4>{gap.title}</h4>
        <p>{gap.description}</p>
        <small>
          Source line {gap.source_line || '-'} | {gap.standard_system || 'N/A'} {gap.standard_code || ''}
        </small>
        {resolved && gap.resolved_at && (
          <small>Reviewed at {new Date(gap.resolved_at).toLocaleString()}</small>
        )}
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
