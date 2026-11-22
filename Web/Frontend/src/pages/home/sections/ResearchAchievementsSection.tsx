import { Award, CheckCircle, ShieldCheck, TrendingDown } from 'lucide-react'

const benchmarks = [
  {
    value: '2.856%',
    label: 'Citywide Out-of-Sample MAPE',
    delta: '45.4% error cut vs. LightGBM+MinT (5.231%)',
    icon: TrendingDown,
  },
  {
    value: '192.67 MW',
    label: 'Daily Peak MAE',
    delta: '18.6% sharper peak accuracy across 180 test days',
    icon: Award,
  },
  {
    value: '87.6%–88.4%',
    label: 'ACI Empirical Coverage',
    delta: 'Raised from 83.11% uncalibrated across all 7 series',
    icon: ShieldCheck,
  },
  {
    value: '+0.291%',
    label: 'NWP Noise Sensitivity',
    delta: 'Minimal MAPE shift under ±1.5°C weather noise',
    icon: CheckCircle,
  },
]

export function ResearchAchievementsSection() {
  return (
    <section className="home-section page-width" aria-labelledby="research-title">
      <div className="section-header-compact">
        <p className="section-kicker">06 · Empirical Validation (2026 Test)</p>
        <h2 id="research-title">Research Achievements &amp; Benchmark Proof</h2>
      </div>

      <div className="bento-4-grid">
        {benchmarks.map(({ value, label, delta, icon: Icon }) => (
          <article className="glass-card glass-card--light achievement-card" key={label}>
            <span className="tile-icon">
              <Icon aria-hidden="true" />
            </span>
            <strong className="achievement-value">{value}</strong>
            <h3>{label}</h3>
            <p>{delta}</p>
          </article>
        ))}
      </div>
    </section>
  )
}