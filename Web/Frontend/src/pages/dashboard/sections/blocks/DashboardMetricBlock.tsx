import type { LucideIcon } from 'lucide-react'

type DashboardMetricBlockProps = {
  title: string
  value: string
  detail: string
  icon: LucideIcon
}

export function DashboardMetricBlock({ title, value, detail, icon: Icon }: DashboardMetricBlockProps) {
  return (
    <article className="dashboard-metric-block">
      <span className="dashboard-metric-icon"><Icon aria-hidden="true" /></span>
      <div>
        <p>{title}</p>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  )
}
