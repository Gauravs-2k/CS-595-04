const severities = ['critical', 'warning', 'info']

export default function Sidebar({ gaps = [] }) {
  return (
    <aside className="tg-sidebar">
      <h3>Priority Snapshot</h3>
      <ul>
        {severities.map((sev) => {
          const count = gaps.filter((gap) => gap.severity === sev && !gap.resolved).length
          return (
            <li key={sev}>
              <span className={`badge badge-${sev}`}>{sev}</span>
              <strong>{count}</strong>
            </li>
          )
        })}
      </ul>
    </aside>
  )
}
