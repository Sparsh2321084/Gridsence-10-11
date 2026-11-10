import { CalendarClock, Zap } from 'lucide-react'

const metrics = [
  { label: 'Current Delhi load', value: '7,245 MW', detail: '↑ 2.3%', icon: Zap },
  { label: 'Next hour forecast', value: '7,380 MW', detail: '↑ 1.9%', icon: CalendarClock },
  { label: 'Last updated', value: '13:45 PM', detail: 'Nov 7, 2026', icon: CalendarClock },
]

export function MetricsSection() {
  return (
    <div className="page-width metrics-wrap">
      <section className="metrics-strip" aria-label="Grid status">
        {metrics.map(({ label, value, detail, icon: Icon }) => (
          <div className="metric" key={label}>
            <span className="metric-icon"><Icon aria-hidden="true" /></span>
            <div className="metric-copy">
              <span className="metric-label">{label}</span>
              <strong>{value}</strong>
              <span className="metric-detail">{detail}</span>
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}
