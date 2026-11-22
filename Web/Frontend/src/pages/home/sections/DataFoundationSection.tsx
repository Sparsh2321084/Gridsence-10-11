import { CheckCircle2, CloudSun, Database, FileSpreadsheet, ShieldAlert } from 'lucide-react'

const dataPillars = [
  {
    stat: '262,752',
    label: '15-Min Intervals',
    detail: '2,737 consecutive days (Apr 2019 – Sep 2026) across 7 series',
    icon: Database,
  },
  {
    stat: '391 Weeks',
    label: 'Ledger Cross-Audit',
    detail: 'Reconciled against official SLDC AMOUNT ACCOUNT settlement sheets',
    icon: FileSpreadsheet,
  },
  {
    stat: '29 Features',
    label: 'Weather & Calendar',
    detail: 'Heat index, 72h thermal inertia, solar irradiance & holiday harmonics',
    icon: CloudSun,
  },
  {
    stat: 'Zero Leaks',
    label: '5-Gate ETL Hygiene',
    detail: 'BIFF8 decryption, date-typo repair, spike filtering & NaN masking',
    icon: ShieldAlert,
  },
]

export function DataFoundationSection() {
  return (
    <section className="home-section page-width" aria-labelledby="data-title">
      <div className="section-header-compact">
        <p className="section-kicker">03 · Audit-Gated Data Foundation</p>
        <h2 id="data-title">Built on 7.5 Years of Verified Delhi SLDC Settlement Archives</h2>
      </div>

      <div className="bento-4-grid">
        {dataPillars.map(({ stat, label, detail, icon: Icon }) => (
          <article className="glass-card glass-card--light bento-stat-card" key={label}>
            <div className="bento-stat-top">
              <span className="tile-icon">
                <Icon aria-hidden="true" />
              </span>
              <span className="bento-stat-num">{stat}</span>
            </div>
            <h3>{label}</h3>
            <p>{detail}</p>
          </article>
        ))}
      </div>

      <div className="glass-strip glass-strip--light">
        <CheckCircle2 aria-hidden="true" />
        <span>
          <strong>Live Ingestion Ready:</strong> Automated 15-minute SLDC portal polling and weekly
          ABT workbook imports feed a quality-aware SQLite store with deterministic{' '}
          <code>LIVE / STALE / REPLAYED</code> guardrails.
        </span>
      </div>
    </section>
  )
}