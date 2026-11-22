import { ArrowRight, CloudRain, Cpu, Radio, Sun } from 'lucide-react'

const roadmap = [
  {
    title: 'Operational NWP Vintages & Ensembles',
    detail: 'Benchmark archived day-ahead NWP runs and multi-seed iTransformer ensembles.',
    icon: CloudRain,
  },
  {
    title: 'Multi-Zone Weather Centroids',
    detail: 'Map localized weather stations to BRPL, TPDDL, BYPL, and NDMC territories.',
    icon: Radio,
  },
  {
    title: 'Rooftop PV Disaggregation',
    detail: 'Separate gross cooling demand from behind-the-meter solar net-load suppression.',
    icon: Sun,
  },
  {
    title: 'IEEE 738-2023 Corridor Pilots',
    detail: 'Extend thermal screening to dynamic conductor ratings on 220/400 kV corridors.',
    icon: Cpu,
  },
]

export function FutureDirectionsSection() {
  return (
    <section className="home-section home-section--last page-width" aria-labelledby="future-title">
      <div className="section-header-compact">
        <p className="section-kicker">07 · Research &amp; Deployment Roadmap</p>
        <h2 id="future-title">Future Directions</h2>
      </div>

      <div className="bento-4-grid">
        {roadmap.map(({ title, detail, icon: Icon }) => (
          <article className="glass-card glass-card--light future-card" key={title}>
            <span className="tile-icon">
              <Icon aria-hidden="true" />
            </span>
            <h3>{title}</h3>
            <p>{detail}</p>
          </article>
        ))}
      </div>

      <div className="glass-card glass-card--light final-cta-strip">
        <div>
          <h3>Ready to inspect the 96-block forecast?</h3>
          <p>Switch between All Delhi SLDC and individual DISCOM dashboards in real time.</p>
        </div>
        <a className="button button--primary" href="/dashboard">
          Go to Dashboard <ArrowRight aria-hidden="true" />
        </a>
      </div>
    </section>
  )
}