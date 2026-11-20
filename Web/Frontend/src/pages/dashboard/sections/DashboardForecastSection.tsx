import { useEffect, useState } from 'react'
import { ArrowRight, BarChart3, RefreshCw } from 'lucide-react'
import { apiUrl } from '../../../lib/api'
import { AreaGridDashboard } from './AreaGridDashboard'
import { MainGridDashboard } from './MainGridDashboard'
import { AreaSwitcher } from './blocks/AreaSwitcher'
import type { DataFreshness, ForecastMode, ForecastResponse, UtilityArea } from './types'

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Unable to load forecast'
}

class ForecastRequestError extends Error {
  readonly dataFreshness: DataFreshness | null

  constructor(message: string, dataFreshness: DataFreshness | null = null) {
    super(message)
    this.dataFreshness = dataFreshness
  }
}

function isDataFreshness(value: unknown): value is DataFreshness {
  if (!value || typeof value !== 'object') return false
  const freshness = value as Partial<DataFreshness>
  return (
    (freshness.forecast_mode === 'LIVE'
      || freshness.forecast_mode === 'STALE'
      || freshness.forecast_mode === 'REPLAYED'
      || freshness.forecast_mode === 'UNAVAILABLE')
    && (freshness.latest_actual_timestamp === null || typeof freshness.latest_actual_timestamp === 'string')
    && (freshness.lag_minutes === null || typeof freshness.lag_minutes === 'number')
    && typeof freshness.valid_blocks_percent === 'number'
    && typeof freshness.filled_blocks === 'number'
  )
}

async function requestForecast(signal?: AbortSignal): Promise<ForecastResponse> {
  const response = await fetch(apiUrl('/api/forecast'), signal ? { signal } : undefined)
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    if (!response.ok) throw new ForecastRequestError(`Forecast API returned ${response.status}`)
    throw new ForecastRequestError('Forecast API returned an invalid response')
  }

  if (!response.ok) {
    const body = payload && typeof payload === 'object'
      ? payload as { detail?: unknown; data_freshness?: unknown }
      : {}
    const detail = body.detail && typeof body.detail === 'object'
      ? body.detail as { message?: unknown; data_freshness?: unknown }
      : {}
    const message = typeof detail.message === 'string'
      ? detail.message
      : typeof body.detail === 'string'
        ? body.detail
        : `Forecast API returned ${response.status}`
    const freshness = isDataFreshness(body.data_freshness)
      ? body.data_freshness
      : isDataFreshness(detail.data_freshness)
        ? detail.data_freshness
        : null
    throw new ForecastRequestError(message, freshness)
  }

  if (!payload || typeof payload !== 'object' || !('forecast' in payload)) {
    throw new ForecastRequestError('Forecast API returned an invalid response')
  }
  return payload as ForecastResponse
}

function formatLag(minutes: number | null) {
  if (minutes === null) return 'Lag unavailable'
  if (minutes < 0) return `Timestamp is ${Math.abs(minutes)} minutes ahead`
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  const remainingMinutes = minutes % 60
  if (days) return `${days} days, ${hours} hours, ${remainingMinutes} minutes`
  if (hours) return `${hours} hours, ${remainingMinutes} minutes`
  return `${remainingMinutes} minutes`
}

function freshnessTitle(mode: ForecastMode) {
  if (mode === 'LIVE') return 'Live actual-load data'
  if (mode === 'STALE') return 'Stale actual-load data'
  if (mode === 'REPLAYED') return 'Historical Replay Mode'
  return 'Actual-load data unavailable'
}

export function DashboardForecastSection() {
  const [data, setData] = useState<ForecastResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [unavailableFreshness, setUnavailableFreshness] = useState<DataFreshness | null>(null)
  const [selectedArea, setSelectedArea] = useState<UtilityArea | null>(null)

  const loadForecast = async () => {
    setLoading(true)
    setError('')
    try {
      setData(await requestForecast())
      setUnavailableFreshness(null)
    } catch (requestError) {
      setError(getErrorMessage(requestError))
      setUnavailableFreshness(
        requestError instanceof ForecastRequestError ? requestError.dataFreshness : null,
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()

    requestForecast(controller.signal)
      .then((forecast) => {
        setData(forecast)
        setUnavailableFreshness(null)
      })
      .catch((requestError: unknown) => {
        if (!controller.signal.aborted) {
          setError(getErrorMessage(requestError))
          setUnavailableFreshness(
            requestError instanceof ForecastRequestError ? requestError.dataFreshness : null,
          )
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [])

  if (loading && !data) {
    return (
      <main className="dashboard-loading page-width">
        <RefreshCw className="dashboard-spinner" aria-hidden="true" />
        <p>Generating Delhi load forecast...</p>
      </main>
    )
  }

  if (error) {
    return (
      <main className="dashboard-error page-width">
        <BarChart3 aria-hidden="true" />
        <p className="section-kicker">Forecast unavailable</p>
        <h1>Forecast could not be generated.</h1>
        <p>{error}</p>
        {unavailableFreshness && (
          <p className={`dashboard-freshness dashboard-freshness--${unavailableFreshness.forecast_mode.toLowerCase()}`} role="status">
            <strong>{freshnessTitle(unavailableFreshness.forecast_mode)}</strong>
            {unavailableFreshness.latest_actual_timestamp
              ? ` · Latest actual: ${new Date(unavailableFreshness.latest_actual_timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}`
              : ''}
          </p>
        )}
        <button className="button button--outline" type="button" onClick={() => void loadForecast()}>
          Retry <RefreshCw aria-hidden="true" />
        </button>
      </main>
    )
  }

  if (!data) return null
  if (data.forecast.length === 0) {
    return (
      <main className="dashboard-error page-width">
        <BarChart3 aria-hidden="true" />
        <p className="section-kicker">Forecast unavailable</p>
        <h1>The API returned no forecast intervals.</h1>
        <button className="button button--outline" type="button" onClick={() => void loadForecast()}>
          Retry <RefreshCw aria-hidden="true" />
        </button>
      </main>
    )
  }

  const freshness = data.data_freshness
  const latestActual = freshness.latest_actual_timestamp
    ? new Date(freshness.latest_actual_timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })
    : 'No valid actuals'

  return (
    <main className="dashboard-live page-width">
      <div className="dashboard-heading">
        <div>
          <p className="section-kicker">GridSense dashboard</p>
          <h1>{selectedArea ? `${selectedArea.label} area dashboard` : 'Delhi grid dashboard'}</h1>
          <p className="dashboard-meta">
            {data.horizon_hours}-hour forecast · {data.interval_minutes}-minute blocks · Generated {new Date(data.generated_at).toLocaleString('en-IN')}
          </p>
          <p className={`dashboard-freshness dashboard-freshness--${freshness.forecast_mode.toLowerCase()}`} role="status">
            <strong>{freshnessTitle(freshness.forecast_mode)}</strong>
            {' · '}Latest actual: {latestActual}
            {freshness.forecast_mode === 'STALE' && ` · Lag: ${formatLag(freshness.lag_minutes)}`}
            {freshness.forecast_mode === 'REPLAYED' && ' · Yesterday comparisons are unavailable'}
            {freshness.forecast_mode === 'LIVE' && ` · ${freshness.valid_blocks_percent}% valid blocks over 7 days`}
            {freshness.filled_blocks > 0 && ` · ${freshness.filled_blocks} short-gap blocks interpolated for model input`}
          </p>
        </div>
        <button className="dashboard-refresh" type="button" onClick={() => void loadForecast()} disabled={loading}>
          <RefreshCw aria-hidden="true" /> Refresh
        </button>
      </div>

      <AreaSwitcher selectedArea={selectedArea} onSelect={setSelectedArea} />

      <p className="dataset-cutoff">
        {data.model_input_source === 'LIVE_ACTUALS'
          ? <>Model input window uses recent actuals through <strong>{new Date(data.data_as_of).toLocaleString('en-IN')}</strong>.</>
          : <>Historical model feature baseline ends at <strong>{new Date(data.data_as_of).toLocaleString('en-IN')}</strong>.</>}
        {' '}Weather source: <strong>{data.weather_source}</strong>.
      </p>

      {selectedArea ? (
        <AreaGridDashboard data={data} area={selectedArea} />
      ) : (
        <MainGridDashboard
          data={data}
          selectedArea={selectedArea}
          onSelectArea={setSelectedArea}
        />
      )}
      <a className="dashboard-home-link" href="/">
        Return home <ArrowRight aria-hidden="true" />
      </a>
    </main>
  )
}
