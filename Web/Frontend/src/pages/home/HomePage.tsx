import { AboutSection } from './sections/AboutSection'
import { CallToActionSection } from './sections/CallToActionSection'
import { HeroSection } from './sections/HeroSection'
import { MetricsSection } from './sections/MetricsSection'
import { ProcessSection } from './sections/ProcessSection'
import { WhyForecastingSection } from './sections/WhyForecastingSection'

export function HomePage() {
  return (
    <main>
      <HeroSection />
      <MetricsSection />
      <AboutSection />
      <WhyForecastingSection />
      <ProcessSection />
      <CallToActionSection />
    </main>
  )
}
