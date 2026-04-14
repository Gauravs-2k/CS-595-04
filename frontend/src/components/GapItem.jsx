export default function GapItem({ gap, onResolve }) {
  return (
    <article className={`gap-item severity-${gap.severity}`}>
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
            checked={Boolean(gap.resolved)}
            onChange={() => onResolve(gap.id)}
            disabled={Boolean(gap.resolved)}
          />
          Mark resolved
        </label>
      </div>
    </article>
  )
}
