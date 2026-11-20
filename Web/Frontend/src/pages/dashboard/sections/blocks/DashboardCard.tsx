import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

type DashboardCardProps = {
  title: string
  icon: LucideIcon
  className?: string
  children: ReactNode
}

export function DashboardCard({ title, icon: Icon, className = '', children }: DashboardCardProps) {
  return (
    <section className={`dashboard-card ${className}`}>
      <header className="dashboard-card-heading">
        <Icon aria-hidden="true" />
        <h2>{title}</h2>
      </header>
      <div className="dashboard-card-content">{children}</div>
    </section>
  )
}
