import { Activity } from 'lucide-react'
import { DashboardCard } from './DashboardCard'
import type { ForecastResponse, ForecastTarget } from '../types'

type ProbabilisticLoadBlockProps = {
  data: ForecastResponse
  target: ForecastTarget
  title: string
  className?: string
}

const chartWidth = 900
const chartHeight = 210
const plotLeft = 58
const plotWidth = chartWidth - plotLeft - 8

function makeLine(values: Array<number | null>, minimum: number, range: number, height = chartHeight) {
  const segments: string[] = []
  let points: string[] = []

  values.forEach((value, index) => {
    if (value === null || !Number.isFinite(value)) {
      if (points.length > 1) segments.push(points.join(' '))
      points = []
      return
    }

    const x = plotLeft + (index / Math.max(values.length - 1, 1)) * plotWidth
    const y = height - ((value - minimum) / range) * height
    points.push(`${x},${y}`)
  })

  if (points.length > 1) segments.push(points.join(' '))
  return segments
}

function WeatherStrip({
  values,
  label,
  unit,
  color,
}: {
  values: Array<number | null>
  label: string
  unit: string
  color: string
}) {
  const valid = values.filter((value): value is number => value !== null && Number.isFinite(value))
  if (valid.length === 0) {
    return <p className="weather-strip-empty">{label}: unavailable</p>
  }

  const minimum = Math.min(...valid)
  const range = Math.max(Math.max(...valid) - minimum, 1)
  const lines = makeLine(values, minimum, range, 40)

  return (
    <div className="weather-strip">
      <div className="weather-strip-label">
        <strong>{label}</strong>
        <span>{minimum.toFixed(0)}–{Math.max(...valid).toFixed(0)} {unit}</span>
      </div>
      <svg viewBox={`0 0 ${chartWidth} 42`} role="img" aria-label={`${label} over forecast period`}>
        {lines.map((points, index) => <polyline key={index} points={points} fill="none" stroke={color} strokeWidth="3" />)}
      </svg>
    </div>
  )
}

export function ProbabilisticLoadBlock({ data, target, title, className = '' }: ProbabilisticLoadBlockProps) {
  const bounds = data.forecast.flatMap((row) => [row[`${target}_p05`], row[`${target}_p95`]])
  const minimum = Math.floor(Math.min(...bounds) / 500) * 500
  const maximum = Math.ceil(Math.max(...bounds) / 500) * 500
  const range = Math.max(maximum - minimum, 1)
  const getX = (index: number) => plotLeft + (index / Math.max(data.forecast.length - 1, 1)) * plotWidth
  const getY = (value: number) => chartHeight - ((value - minimum) / range) * chartHeight
  const median = data.forecast.map((row, index) => `${getX(index)},${getY(row[target])}`).join(' ')
  const band = [
    ...data.forecast.map((row, index) => `${getX(index)},${getY(row[`${target}_p95`])}`),
    ...data.forecast.map((row, index) => `${getX(index)},${getY(row[`${target}_p05`])}`).reverse(),
  ].join(' ')
  const actualLines = makeLine(
    data.forecast.map((row) => row.yesterday_actuals[target]),
    minimum,
    range,
  )
  const hasYesterdayActuals = data.forecast.some((row) =>
    row.yesterday_actuals[target] !== null && Number.isFinite(row.yesterday_actuals[target]),
  )

  return (
    <DashboardCard title={title} icon={Activity} className={className}>
      <div className="forecast-legend">
        <span><i className="forecast-legend-line" /> P50 forecast</span>
        <span><i className="forecast-legend-band" /> P05–P95 band</span>
        {hasYesterdayActuals && <span><i className="forecast-legend-actual" /> Yesterday actual</span>}
      </div>
      <svg
        className="forecast-chart"
        viewBox={`0 0 ${chartWidth} 248`}
        role="img"
        aria-label={`${title}: median forecast with P05 to P95 range and yesterday actuals when available`}
      >
        {[0, 1, 2, 3, 4].map((step) => {
          const y = (chartHeight / 4) * step
          const value = maximum - (range / 4) * step
          return (
            <g key={step}>
              <line x1={plotLeft} x2={chartWidth} y1={y} y2={y} className="chart-grid-line" />
              <text x={plotLeft - 8} y={Math.max(y + 4, 10)} textAnchor="end" className="chart-label">
                {Math.round(value).toLocaleString('en-IN')}
              </text>
            </g>
          )
        })}
        <polygon points={band} className="chart-confidence-band" />
        {actualLines.map((points, index) => (
          <polyline key={index} points={points} className="chart-yesterday-line" />
        ))}
        <polyline points={median} className="chart-demand-line" />
        {data.forecast.map((row, index) => {
          if (index !== 0 && index % 24 !== 0 && index !== data.forecast.length - 1) return null
          const anchor = index === 0 ? 'start' : index === data.forecast.length - 1 ? 'end' : 'middle'
          const time = new Date(row.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
          return <text key={row.timestamp} x={getX(index)} y="240" textAnchor={anchor} className="chart-label">{time}</text>
        })}
      </svg>
      <div
        className="ramp-severity-strip"
        role="img"
        aria-label={`${title} 15-minute ramp severity across the forecast`}
      >
        {data.forecast.map((row) => {
          const ramp = row.ramp_assessments[target]
          const severity = ramp.severity?.toLowerCase() ?? 'unavailable'
          const description = ramp.absolute_change_mw === null
            ? 'Ramp unavailable: no adjacent actual block'
            : `${ramp.severity} ramp · ${ramp.absolute_change_mw.toFixed(1)} MW change`
          return (
            <span
              key={row.timestamp}
              className={`ramp-severity-block ramp-severity-block--${severity}`}
              title={`${new Date(row.timestamp).toLocaleString('en-IN')} · ${description}`}
            />
          )
        })}
      </div>
      <div className="ramp-severity-legend" aria-label="Ramp severity legend">
        <span><i className="ramp-severity-swatch ramp-severity-swatch--normal" /> Normal</span>
        <span><i className="ramp-severity-swatch ramp-severity-swatch--moderate" /> Moderate</span>
        <span><i className="ramp-severity-swatch ramp-severity-swatch--severe" /> Severe</span>
        <span><i className="ramp-severity-swatch ramp-severity-swatch--unavailable" /> Unavailable</span>
      </div>
      <p className="ramp-threshold-note">
        {target.toUpperCase()} thresholds: P75 {data.ramp_thresholds_mw[target].p75.toFixed(1)} MW ·
        {' '}P95 {data.ramp_thresholds_mw[target].p95.toFixed(1)} MW per 15 minutes
      </p>
      <div className="weather-strip-grid">
        <WeatherStrip
          values={data.forecast.map((row) => row.weather.apparent_temperature)}
          label="Apparent temperature"
          unit="°C"
          color="#e88742"
        />
        <WeatherStrip
          values={data.forecast.map((row) => row.weather.shortwave_radiation)}
          label="Shortwave radiation"
          unit="W/m²"
          color="#e2aa37"
        />
      </div>
    </DashboardCard>
  )
}
