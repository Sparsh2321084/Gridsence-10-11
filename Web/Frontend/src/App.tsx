import './App.css'
import { SiteFooter } from './components/layout/SiteFooter'
import { SiteHeader } from './components/layout/SiteHeader'
import { DashboardPlaceholder } from './sections/dashboard/DashboardPlaceholder'
import { AboutSection } from './sections/home/AboutSection'
import { CallToActionSection } from './sections/home/CallToActionSection'
import { HeroSection } from './sections/home/HeroSection'
import { MetricsSection } from './sections/home/MetricsSection'
import { ProcessSection } from './sections/home/ProcessSection'
import { WhyForecastingSection } from './sections/home/WhyForecastingSection'

function HomePage() {
  return (
    <>
      <SiteHeader />
      <main>
        <HeroSection />
        <MetricsSection />
        <AboutSection />
        <WhyForecastingSection />
        <ProcessSection />
        <CallToActionSection />
      </main>
      <SiteFooter />
    </>
  )
}

export default function App() {
  return window.location.pathname.replace(/\/$/, '') === '/dashboard'
    ? <DashboardPlaceholder />
    : <HomePage />
}
