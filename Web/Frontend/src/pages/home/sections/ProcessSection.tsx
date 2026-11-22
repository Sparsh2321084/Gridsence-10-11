import { Cpu, Database, GitMerge, ShieldCheck } from 'lucide-react'

const steps = [
  {
    step: '01',
    title: 'Audit-Gated Lookback',
    detail: 'Assembles 672 trailing 15-min load blocks (7 days) plus 29 weather & calendar covariates.',
    icon: Database,
  },
  {
    step: '02',
    title: 'Multi-Entity iTransformer',
    detail: 'Applies variable-axis self-attention across 36 tokens to learn cross-utility coupling.',
    icon: Cpu,
  },
  {
    step: '03',
    title: 'MinT + Causal Calibration',
    detail: 'Reconciles physical MW sums via MinT and removes secular bias with a 14-day rolling corrector.',
    icon: GitMerge,
  },
  {
    step: '04',
    title: 'Adaptive Conformal Bounds',
    detail: 'Outputs calibrated P05–P50–P95 intervals every 15 minutes for reserve and market sizing.',
    icon: ShieldCheck,
  },
]

export function ProcessSection() {
  return (
    <section className="home-section page-width" id="how-it-works" aria-labelledby="process-title">
      <div className="section-header-compact">
        <p className="section-kicker">04 · System Architecture</p>
        <h2 id="process-title">How GridSense Works</h2>
      </div>

      <div className="bento-4-grid">
        {steps.map(({ step, title, detail, icon: Icon }) => (
          <article className="glass-card glass-card--light process-glass-card" key={step}>
            <div className="process-glass-head">
              <span className="step-pill">{step}</span>
              <span className="tile-icon">
                <Icon aria-hidden="true" />
              </span>
            </div>
            <h3>{title}</h3>
            <p>{detail}</p>
          </article>
        ))}
      </div>
    </section>
  )
}