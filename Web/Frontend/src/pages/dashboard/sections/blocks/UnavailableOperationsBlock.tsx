import type { LucideIcon } from 'lucide-react'
import { DashboardCard } from './DashboardCard'

type UnavailableOperationsBlockProps = {
  title: string
  icon: LucideIcon
  requiredData: string
  className?: string
}

export function UnavailableOperationsBlock({
  title,
  icon,
  requiredData,
  className = '',
}: UnavailableOperationsBlockProps) {
  return (
    <DashboardCard title={title} icon={icon} className={className}>
      <span className="data-connection-badge">Not connected</span>
      <p className="operations-unavailable">
        This panel is not generating operational alerts or dispatch advice.
      </p>
      <p className="dashboard-card-caption">Required data: {requiredData}</p>
    </DashboardCard>
  )
}
