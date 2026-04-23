export default function TopBar({ title, subtitle }) {
  return (
    <header className="tg-topbar">
      <div>
        <p className="tg-eyebrow">TransitionGuard</p>
        <h1>{title}</h1>
        {subtitle ? <p className="tg-subtitle">{subtitle}</p> : null}
      </div>
    </header>
  )
}
