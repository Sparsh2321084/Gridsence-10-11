import {
  AlertTriangle,
  Building2,
  Flame,
  GitBranch,
  IndianRupee,
  MoonStar,
  Unplug,
} from 'lucide-react'

const challenges = [
  {
    title: 'Asynchronous Consumer Peaks',
    detail:
      'Residential DISCOMs (BRPL, BYPL) surge between 22:30–00:30 IST from overnight cooling, while commercial NDMC peaks sharply at 12:45–16:00 IST.',
    icon: MoonStar,
  },
  {
    title: '52 Feeder Boundary Shifts',
    detail:
      'Periodic 11 kV / 33 kV feeder transfers between neighboring DISCOMs create step jumps in isolated utility meters while total city load remains smooth.',
    icon: GitBranch,
  },
  {
    title: 'Multi-Day Heat & Rooftop PV',
    detail:
      '72-hour urban heat retention elevates night cooling baselines, while behind-the-meter solar depresses midday drawal and steepens sunset ramps.',
    icon: Building2,
  },
]

const stakes = [
  {
    title: 'Conductor Thermal Sag',
    metric: '> 43°C Ambient + I²R',
    detail:
      'Heavy afternoon current expands 220 kV / 400 kV overhead conductors, reducing ground clearance and risking phase-to-ground flashovers.',
    icon: Flame,
  },
  {
    title: 'Transformer Insulation Stress',
    metric: '23:15 Night Peak',
    detail:
      'When overnight temperatures stay above 33°C during heatwaves, oil-immersed 66/11 kV transformers cannot shed heat before midnight AC surges.',
    icon: AlertTriangle,
  },
  {
    title: 'N-1 Cascades & DSM Penalties',
    metric: 'CERC 15-Min Settlement',
    detail:
      'Single-line thermal trips shift load onto parallel corridors, while unscheduled 15-minute drawal deviations trigger punitive CERC DSM charges.',
    icon: IndianRupee,
  },
]

export function ChallengesAndStakesSection() {
  return (
    <section className="home-section page-width" aria-labelledby="challenges-title">
      <div className="section-header-compact">
        <p className="section-kicker">02 · Grid Complexity &amp; Outage Risk</p>
        <h2 id="challenges-title">
          Why Delhi&apos;s Grid Is Hard to Predict—and What Happens When Forecasts Miss
        </h2>
      </div>

      <div className="stakes-split">
        <div className="glass-card glass-card--light stakes-panel">
          <div className="panel-tag">
            <Unplug aria-hidden="true" /> Forecasting Challenges
          </div>
          <h3>Heterogeneous &amp; Shifting Load</h3>
          <div className="compact-stack">
            {challenges.map(({ title, detail, icon: Icon }) => (
              <article className="glass-subcard glass-subcard--light" key={title}>
                <span className="tile-icon">
                  <Icon aria-hidden="true" />
                </span>
                <div>
                  <h4>{title}</h4>
                  <p>{detail}</p>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="glass-card glass-card--dark stakes-panel">
          <div className="panel-tag panel-tag--amber">
            <AlertTriangle aria-hidden="true" /> Physical &amp; Market Impact
          </div>
          <h3>Disturbances &amp; Outage Consequences</h3>
          <div className="compact-stack">
            {stakes.map(({ title, metric, detail, icon: Icon }) => (
              <article className="glass-subcard glass-subcard--dark" key={title}>
                <span className="tile-icon tile-icon--amber">
                  <Icon aria-hidden="true" />
                </span>
                <div>
                  <div className="subcard-head">
                    <h4>{title}</h4>
                    <span className="micro-badge">{metric}</span>
                  </div>
                  <p>{detail}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}