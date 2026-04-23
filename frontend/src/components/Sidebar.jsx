const CATEGORIES = [
  { key: 'missing_from_pcp', label: 'New from Handoff', badge: 'critical' },
  { key: 'missing_from_handoff', label: 'Not in Handoff', badge: 'info' },
  { key: 'changed', label: 'Changed', badge: 'warning' },
  { key: 'action_needed', label: 'Action Items', badge: 'critical' },
]

export default function Sidebar({ gaps = [] }) {
  const total = gaps.filter((g) => !g.resolved).length
  const reviewed = gaps.filter((g) => g.resolved).length

  return (
    <aside className="tg-sidebar" role="complementary" aria-label="Gap summary">
      <h3>Gap Summary</h3>
      <ul>
        {CATEGORIES.map(({ key, label, badge }) => {
          const count = gaps.filter((g) => g.category === key && !g.resolved).length
          if (count === 0) return null
          return (
            <li key={key}>
              <span className={`badge badge-${badge}`}>{label}</span>
              <strong>{count}</strong>
            </li>
          )
        })}
      </ul>
      <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--border)', fontSize: '0.85rem' }}>
        <p style={{ margin: '4px 0' }}><strong>{total}</strong> unresolved</p>
        <p style={{ margin: '4px 0', color: 'var(--info)' }}><strong>{reviewed}</strong> reviewed</p>
      </div>
    </aside>
  )
}
