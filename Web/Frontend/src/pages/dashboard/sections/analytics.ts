import type { ForecastRow, ForecastTarget } from './types'

export function getPeakRow(rows: ForecastRow[], target: ForecastTarget) {
  return rows.reduce((peak, row) => row[target] > peak[target] ? row : peak)
}

export function getP95PeakRow(rows: ForecastRow[], target: ForecastTarget) {
  return rows.reduce((peak, row) =>
    row[`${target}_p95`] > peak[`${target}_p95`] ? row : peak,
  )
}

export function getDailyEnergyMu(rows: ForecastRow[], target: ForecastTarget, intervalMinutes: number) {
  const megawattHours = rows.reduce((sum, row) => sum + row[target] * intervalMinutes / 60, 0)
  return megawattHours / 1000
}

export function getYesterdayPeak(rows: ForecastRow[], target: ForecastTarget) {
  const actuals = rows
    .map((row) => row.yesterday_actuals[target])
    .filter((value): value is number => value !== null && Number.isFinite(value))

  return actuals.length ? Math.max(...actuals) : null
}

export function getSteepestRamp(rows: ForecastRow[], target: ForecastTarget) {
  return rows.slice(1).reduce(
    (steepest, row, index) => {
      const change = row[target] - rows[index][target]
      return Math.abs(change) > Math.abs(steepest.change)
        ? { change, timestamp: row.timestamp }
        : steepest
    },
    { change: 0, timestamp: rows[0].timestamp },
  )
}

export function getPercentChange(value: number, baseline: number | null) {
  return baseline !== null && baseline !== 0 ? ((value - baseline) / baseline) * 100 : null
}
