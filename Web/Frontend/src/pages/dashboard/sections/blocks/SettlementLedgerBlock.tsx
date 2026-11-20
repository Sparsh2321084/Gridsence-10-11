import { Download, TableProperties } from 'lucide-react'
import { DashboardCard } from './DashboardCard'
import type { ForecastRow, ForecastTarget } from '../types'

type SettlementLedgerBlockProps = {
  forecast: ForecastRow[]
  target: ForecastTarget
  applied: boolean
  className?: string
}

const formatMw = (value: number) =>
  new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 }).format(value)

function escapeCsv(value: string | number) {
  return `"${String(value).replaceAll('"', '""')}"`
}

export function SettlementLedgerBlock({ forecast, target, applied, className = '' }: SettlementLedgerBlockProps) {
  const rows = forecast.map((row) => {
    const dispatch = row.ppa_dispatch
    return {
      timestamp: row.timestamp,
      p05: row[`${target}_p05`],
      p50: row[target],
      p95: row[`${target}_p95`],
      ppa: dispatch?.contracted_ppa_mw ?? null,
      netBid: dispatch?.net_position_mw ?? null,
      reserve: row.required_reserve_mw[target],
      rtmBuffer: dispatch?.rtm_reserve_buffer_mw ?? null,
      status: dispatch?.iex_dam_action ?? 'Apply PPA',
    }
  })

  const downloadCsv = () => {
    const header = ['Time Block', 'P05 MW', 'P50 MW', 'P95 MW', 'PPA MW', 'Required reserve MW', 'Net position MW', 'RTM reserve buffer MW', 'IEX DAM planning action']
    const lines = [
      header.map(escapeCsv).join(','),
      ...rows.map((row) => [
        row.timestamp,
        formatMw(row.p05),
        formatMw(row.p50),
        formatMw(row.p95),
        row.ppa === null ? '' : formatMw(row.ppa),
        formatMw(row.reserve),
        row.netBid === null ? '' : formatMw(row.netBid),
        row.rtmBuffer === null ? '' : formatMw(row.rtmBuffer),
        row.status,
      ].map(escapeCsv).join(',')),
    ]
    const file = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(file)
    const link = document.createElement('a')
    link.href = url
    link.download = 'gridsense-forecast-ledger.csv'
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return (
    <DashboardCard title="96-block forecast ledger" icon={TableProperties} className={`dashboard-card--ledger ${className}`}>
      <button type="button" className="ledger-download" onClick={downloadCsv}>
        <Download aria-hidden="true" /> Download CSV
      </button>
      <p className="dashboard-card-caption">
        {applied
          ? 'Server-calculated planning comparison only; no IEX bid or dispatch instruction is submitted.'
          : 'Enter a PPA value and apply it to load server-calculated reserve and net-position fields.'}
      </p>
      <div className="ledger-scroll">
        <table className="settlement-ledger">
          <thead>
            <tr>
              <th>Time block</th><th>P05</th><th>P50</th><th>P95</th>
              <th>PPA</th><th>Reserve</th><th>Net position</th><th>RTM buffer</th><th>IEX DAM</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.timestamp}>
                <td>{new Date(row.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</td>
                <td>{formatMw(row.p05)}</td>
                <td>{formatMw(row.p50)}</td>
                <td>{formatMw(row.p95)}</td>
                <td>{row.ppa === null ? '—' : formatMw(row.ppa)}</td>
                <td>{formatMw(row.reserve)}</td>
                <td>{row.netBid === null ? '—' : `${row.netBid > 0 ? '+' : ''}${formatMw(row.netBid)}`}</td>
                <td>{row.rtmBuffer === null ? '—' : formatMw(row.rtmBuffer)}</td>
                <td><span className="ledger-status">{row.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </DashboardCard>
  )
}
