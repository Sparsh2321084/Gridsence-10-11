import { useMemo } from 'react'
import { Activity, Gauge, ShieldAlert, Zap } from 'lucide-react'
import { getDailyEnergyMu, getPercentChange, getPeakRow, getP95PeakRow, getYesterdayPeak } from './analytics'
import { AssetSimulatorsBlock } from './blocks/AssetSimulatorsBlock'
import { DashboardMetricBlock } from './blocks/DashboardMetricBlock'
import { ProbabilisticLoadBlock } from './blocks/ProbabilisticLoadBlock'
import { UtilityPeakBlock } from './blocks/UtilityPeakBlock'
import { DashboardCard } from './blocks/DashboardCard'
import type { ForecastResponse, UtilityArea } from './types'

type MainGridDashboardProps = {
  data: ForecastResponse
  selectedArea: UtilityArea | null
  onSelectArea: (area: UtilityArea) => void
}

const formatMw = (value: number) =>
  new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 }).format(value)

function formatPercent(value: number | null) {
  if (value === null) return 'Yesterday actual unavailable'
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}% vs yesterday`
}

export function MainGridDashboard({ data, selectedArea, onSelectArea }: MainGridDashboardProps) {
  const analysis = useMemo(() => {
    const peak = getPeakRow(data.forecast, 'delhi_total_mw')
    const p95Peak = getP95PeakRow(data.forecast, 'delhi_total_mw')
    const yesterdayPeak = getYesterdayPeak(data.forecast, 'delhi_total_mw')
    const reserveSpread = p95Peak.delhi_total_mw_p95 - p95Peak.delhi_total_mw
    const ramp = data.ramp_summary.delhi_total_mw
    return {
      peak,
      p95Peak,
      reserveSpread,
      ramp,
      reserveRequirement: p95Peak.required_reserve_mw.delhi_total_mw,
      energyMu: getDailyEnergyMu(data.forecast, 'delhi_total_mw', data.interval_minutes),
      peakChange: getPercentChange(peak.delhi_total_mw, yesterdayPeak),
    }
  }, [data])

  const metrics = [
    {
      title: 'Expected peak · P50',
      value: `${formatMw(analysis.peak.delhi_total_mw)} MW`,
      detail: `${new Date(analysis.peak.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} · ${formatPercent(analysis.peakChange)}`,
      icon: Zap,
    },
    {
      title: 'P95 ceiling · ACI',
      value: `${formatMw(analysis.p95Peak.delhi_total_mw_p95)} MW`,
      detail: `+${formatMw(analysis.reserveSpread)} MW P95–P50 spread at ceiling`,
      icon: ShieldAlert,
    },
    {
      title: data.thermal_coal_burn.label,
      value: `${formatMw(data.thermal_coal_burn.estimated_coal_burn_tonnes)} t`,
      detail: `${analysis.energyMu.toFixed(1)} MU · ${(data.thermal_coal_burn.thermal_mix_share * 100).toFixed(0)}% thermal-mix planning estimate`,
      icon: Activity,
    },
    {
      title: 'Daily maximum 15-minute ramp',
      value: analysis.ramp.absolute_change_mw === null
        ? 'Unavailable'
        : `${formatMw(analysis.ramp.absolute_change_mw)} MW`,
      detail: analysis.ramp.timestamp && analysis.ramp.severity
        ? `${new Date(analysis.ramp.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} · ${analysis.ramp.severity}`
        : 'No adjacent predecessor available for ramp calculation',
      icon: Gauge,
    },
  ]

  return (
    <>
      <section className="dashboard-section">
        <div className="dashboard-section-heading">
          <div><span>01</span><h2>Executive KPI strip</h2></div>
          <p>Forecast-derived city indicators · MW and MU</p>
        </div>
        <div className="dashboard-metric-grid">
          {metrics.map((metric) => <DashboardMetricBlock key={metric.title} {...metric} />)}
        </div>
      </section>

      <section className="dashboard-section">
        <div className="dashboard-section-heading">
          <div><span>02</span><h2>Primary forecast & weather drivers</h2></div>
          <p>96 forecast blocks · P05–P50–P95</p>
        </div>
        <div className="dashboard-block-grid">
          <ProbabilisticLoadBlock
            data={data}
            target="delhi_total_mw"
            title="Delhi probabilistic load curve"
            className="dashboard-card--8"
          />
          <UtilityPeakBlock
            peak={analysis.peak}
            selectedArea={selectedArea}
            onSelect={onSelectArea}
          />
        </div>
      </section>

      <section className="dashboard-section">
        <div className="dashboard-section-heading">
          <div><span>03</span><h2>Grid protection & market operations</h2></div>
          <p>Operational advice requires approved grid and market inputs</p>
        </div>
        <div className="dashboard-block-grid">
          <DashboardCard title="Reserve & dispatch planning signal" icon={Gauge} className="dashboard-card--12">
            <div className="dispatch-signal">
              <span className="data-connection-badge">Planning estimate</span>
              <strong>{formatMw(analysis.reserveRequirement)} MW</strong>
              <p>Estimated reserve at the P95 peak interval using the configured 5% P50 floor.</p>
            </div>
            <p className="dashboard-card-caption">
              Forecast-derived only; not an operator dispatch instruction. Generation availability and live IEX data are not connected.
            </p>
          </DashboardCard>
        </div>
      </section>

      <section className="dashboard-section">
        <div className="dashboard-section-heading">
          <div><span>04</span><h2>Configurable asset simulators</h2></div>
          <p>Editable forecast-based examples · never live telemetry or dispatch</p>
        </div>
        <AssetSimulatorsBlock
          key={`${data.generated_at}:delhi_total_mw`}
          data={data}
          target="delhi_total_mw"
        />
      </section>
    </>
  )
}
