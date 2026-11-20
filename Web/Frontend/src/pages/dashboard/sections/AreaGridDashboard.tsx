import { useMemo, useState } from 'react'
import { Activity, Building2, Gauge, ShieldAlert } from 'lucide-react'
import { apiUrl } from '../../../lib/api'
import { getDailyEnergyMu, getPeakRow } from './analytics'
import { AssetSimulatorsBlock } from './blocks/AssetSimulatorsBlock'
import { DashboardMetricBlock } from './blocks/DashboardMetricBlock'
import { PpaBidCalculatorBlock } from './blocks/PpaBidCalculatorBlock'
import { ProbabilisticLoadBlock } from './blocks/ProbabilisticLoadBlock'
import { SettlementLedgerBlock } from './blocks/SettlementLedgerBlock'
import type { ForecastResponse, UtilityArea } from './types'

type AreaGridDashboardProps = {
  data: ForecastResponse
  area: UtilityArea
}

const formatMw = (value: number) =>
  new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 }).format(value)

export function AreaGridDashboard({ data, area }: AreaGridDashboardProps) {
  const [contractMw, setContractMw] = useState('')
  const [dispatchForecast, setDispatchForecast] = useState<ForecastResponse | null>(null)
  const [dispatchError, setDispatchError] = useState('')
  const [applyingPpa, setApplyingPpa] = useState(false)
  const metrics = useMemo(() => {
    const peak = getPeakRow(data.forecast, area.target)
    const share = peak.delhi_total_mw > 0 ? (peak[area.target] / peak.delhi_total_mw) * 100 : 0
    const p95AtPeak = peak[`${area.target}_p95`]
    return [
      {
        title: 'Area peak · P50 / P95',
        value: `${formatMw(peak[area.target])} MW`,
        detail: `${new Date(peak.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} · P95 ${formatMw(p95AtPeak)} MW`,
        icon: Gauge,
      },
      {
        title: 'Share of Delhi at area peak',
        value: `${share.toFixed(1)}%`,
        detail: 'Historical MAPE unavailable · no backtest metrics in API',
        icon: Activity,
      },
      {
        title: 'Area daily energy',
        value: `${getDailyEnergyMu(data.forecast, area.target, data.interval_minutes).toFixed(1)} MU`,
        detail: 'Integrated from 15-minute P50 values',
        icon: Building2,
      },
      {
        title: 'Archetype sensitivity',
        value: 'Not validated',
        detail: 'No approved area-specific model classification',
        icon: ShieldAlert,
      },
    ]
  }, [area, data])

  const applyPpa = async () => {
    setApplyingPpa(true)
    setDispatchError('')
    try {
      const response = await fetch(apiUrl('/api/forecast'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contracted_ppa_mw: Number(contractMw),
          target: area.target,
        }),
      })
      const payload: unknown = await response.json()
      if (!response.ok) {
        const detail = payload && typeof payload === 'object' && 'detail' in payload
          ? String(payload.detail)
          : `Forecast API returned ${response.status}`
        throw new Error(detail)
      }
      if (
        !payload
        || typeof payload !== 'object'
        || !('forecast' in payload)
        || !Array.isArray(payload.forecast)
        || !payload.forecast.every((row) =>
          row && typeof row === 'object' && 'ppa_dispatch' in row && row.ppa_dispatch !== null,
        )
      ) {
        throw new Error('Forecast API response did not include PPA dispatch calculations')
      }
      setDispatchForecast(payload as ForecastResponse)
    } catch (error) {
      setDispatchForecast(null)
      setDispatchError(error instanceof Error ? error.message : 'Unable to calculate PPA dispatch')
    } finally {
      setApplyingPpa(false)
    }
  }

  return (
    <>
      <section className="dashboard-section">
        <div className="dashboard-section-heading">
          <div><span>01</span><h2>{area.label} KPI strip</h2></div>
          <p>Area forecasts use the same 15-minute horizon and uncertainty bounds</p>
        </div>
        <div className="dashboard-metric-grid">
          {metrics.map((metric) => <DashboardMetricBlock key={metric.title} {...metric} />)}
        </div>
      </section>

      <section className="dashboard-section">
        <div className="dashboard-section-heading">
          <div><span>02</span><h2>Area curve & PPA trading desk</h2></div>
          <p>Planning tools only · no market bid is submitted</p>
        </div>
        <div className="dashboard-block-grid">
          <ProbabilisticLoadBlock
            data={data}
            target={area.target}
            title={`${area.label} probabilistic load curve`}
            className="dashboard-card--7"
          />
          <PpaBidCalculatorBlock
            contractMw={contractMw}
            onContractChange={setContractMw}
            onApply={() => void applyPpa()}
            applying={applyingPpa}
            error={dispatchError}
          />
        </div>
      </section>

      <section className="dashboard-section">
        <div className="dashboard-section-heading">
          <div><span>03</span><h2>Area settlement & simulator planning</h2></div>
          <p>Forecast estimates only · no market bid or asset command is issued</p>
        </div>
        <div className="dashboard-block-grid">
          <SettlementLedgerBlock
            forecast={dispatchForecast?.forecast ?? data.forecast}
            target={area.target}
            applied={dispatchForecast !== null}
            className="dashboard-card--12"
          />
        </div>
        <AssetSimulatorsBlock
          key={`${data.generated_at}:${area.target}`}
          data={data}
          target={area.target}
        />
      </section>
    </>
  )
}
