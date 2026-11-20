import { PieChart } from 'lucide-react'
import { DashboardCard } from './DashboardCard'
import { utilityAreas } from '../types'
import type { ForecastRow, UtilityArea } from '../types'

type UtilityPeakBlockProps = {
  peak: ForecastRow
  selectedArea: UtilityArea | null
  onSelect: (area: UtilityArea) => void
}

const formatMw = (value: number) =>
  new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 }).format(value)

export function UtilityPeakBlock({ peak, selectedArea, onSelect }: UtilityPeakBlockProps) {
  const total = peak.delhi_total_mw

  return (
    <DashboardCard title="DISCOM split at city peak" icon={PieChart} className="dashboard-card--utility-peak">
      <p className="dashboard-card-caption">
        {new Date(peak.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} · {formatMw(total)} MW city demand
      </p>
      <div className="utility-stack" aria-label="Utility demand shares at the Delhi peak">
        {utilityAreas.map((area) => {
          const share = total > 0 ? (peak[area.target] / total) * 100 : 0
          return <span key={area.id} className={`utility-stack-${area.id}`} style={{ width: `${share}%` }} />
        })}
      </div>
      <div className="utility-peak-list">
        {utilityAreas.map((area) => {
          const value = peak[area.target]
          const share = total > 0 ? (value / total) * 100 : 0
          return (
            <button
              type="button"
              key={area.id}
              className={selectedArea?.id === area.id ? 'selected' : ''}
              onClick={() => onSelect(area)}
              aria-label={`Show ${area.label} dashboard, ${formatMw(value)} megawatts, ${share.toFixed(1)} percent of city peak`}
            >
              <span className={`utility-dot utility-dot-${area.id}`} />
              <span>{area.label}</span>
              <strong>{formatMw(value)} MW</strong>
              <small>{share.toFixed(1)}%</small>
            </button>
          )
        })}
      </div>
      <p className="dashboard-card-caption">Select a utility row to open its area dashboard.</p>
    </DashboardCard>
  )
}
