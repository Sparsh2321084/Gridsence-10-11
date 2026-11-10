import { ArrowDownRight, ArrowRight, BarChart3 } from 'lucide-react'
import { SiteHeader } from '../../components/layout/SiteHeader'

export function DashboardPlaceholder() {
  return (
    <div className="dashboard-page">
      <SiteHeader dashboard />
      <main className="dashboard-placeholder page-width">
        <span className="dashboard-symbol"><BarChart3 aria-hidden="true" /></span>
        <p className="section-kicker">GridSense dashboard</p>
        <h1>
          Live insights are
          <br />
          <span>coming online.</span>
        </h1>
        <p>
          Dashboard data will appear here once the backend and forecasting model are connected.
        </p>
        <div className="connection-state">
          <span />
          <span>Data connection not configured</span>
        </div>
        <a className="button button--outline" href="/">
          Return home <ArrowRight aria-hidden="true" />
        </a>
        <div className="dashboard-footnote">
          <ArrowDownRight aria-hidden="true" />
          Live load and forecast values will be supplied by the GridSense API.
        </div>
      </main>
    </div>
  )
}
