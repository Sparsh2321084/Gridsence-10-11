import { Activity, ArrowRight, BarChart3, Cpu, Database } from 'lucide-react'

const processSteps = [
  { title: <>Collect<br />live data</>, icon: Database },
  { title: <>Apply machine<br />learning models</>, icon: Cpu },
  { title: <>Forecast<br />electricity demand</>, icon: BarChart3 },
  { title: <>Visualize<br />grid insights</>, icon: Activity },
]

export function ProcessSection() {
  return (
    <section className="process-section page-width" id="how-it-works" aria-labelledby="process-title">
      <p className="section-kicker">From raw signals to useful insight</p>
      <h2 id="process-title">How GridSense Works</h2>
      <p className="process-intro">From data to insights in a few simple steps.</p>

      <div className="process-steps">
        {processSteps.map(({ title, icon: Icon }, index) => (
          <div className="process-step" key={index}>
            <span className="process-icon"><Icon aria-hidden="true" /></span>
            <p>{title}</p>
            {index < processSteps.length - 1 && (
              <ArrowRight className="step-arrow" aria-hidden="true" />
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
