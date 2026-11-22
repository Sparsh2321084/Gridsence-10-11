import { ArrowLeftRight, FlameKindling, Gauge, ShieldPlus } from 'lucide-react'

const modules = [
  {
    tag: 'DISCOM Trading Desks',
    title: 'IEX Day-Ahead Market (DAM) Net-Position Solver',
    detail:
      'Compares 96-block P50 forecasts against contracted long-term PPAs prior to the 13:00 gate closure to generate exact 15-minute buy and sell bids.',
    icon: ArrowLeftRight,
  },
  {
    tag: 'SLDC Control Room',
    title: 'CERC Spinning Reserve Adequacy Signal',
    detail:
      'Computes block-level reserve buffers from the P95–P50 conformal spread (with a 5% P50 floor) to size fast-ramping gas and RTM reserves.',
    icon: ShieldPlus,
  },
  {
    tag: 'ABT Settlement Risk',
    title: '15-Minute Ramp Severity Classifier',
    detail:
      'Flags steep morning commercial pick-ups and post-sunset rooftop-solar drops against empirical P75 and P95 historical ramp thresholds.',
    icon: Gauge,
  },
  {
    tag: 'Fuel & Supply Logistics',
    title: 'Indicative Thermal Coal-Burn Budgeting',
    detail:
      'Converts integrated daily MWh demand into normative coal tonnage estimates (0.65 t/MWh) to anticipate August–October monsoon fuel bottlenecks.',
    icon: FlameKindling,
  },
]

export function DecisionSupportSection() {
  return (
    <section className="home-section page-width" aria-labelledby="decision-title">
      <div className="decision-layout">
        <div className="decision-intro">
          <p className="section-kicker">05 · Beyond Forecasting</p>
          <h2 id="decision-title">
            Turning 96-Block Numbers into <span>Operational Decisions</span>
          </h2>
          <p>
            Raw megawatt tables do not run a control room. GridSense translates probabilistic curves
            directly into market bids, reserve margins, ramp alerts, and fuel budgets.
          </p>

          <figure className="glass-card glass-card--light decision-figure">
            <img
              src="/forecast-delhi.svg"
              alt="Delhi grid demand forecast curve with confidence intervals"
            />
            <figcaption>
              <span className="status-pulse" /> 96-Block Settlement &amp; Reserve Workflow
            </figcaption>
          </figure>
        </div>

        <div className="decision-grid">
          {modules.map(({ tag, title, detail, icon: Icon }) => (
            <article className="glass-card glass-card--light decision-card" key={title}>
              <div className="decision-card-top">
                <span className="tile-icon">
                  <Icon aria-hidden="true" />
                </span>
                <span className="micro-tag">{tag}</span>
              </div>
              <h3>{title}</h3>
              <p>{detail}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}