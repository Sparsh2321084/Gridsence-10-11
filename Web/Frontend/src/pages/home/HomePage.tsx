import { HeroSection } from './sections/HeroSection'
import { AboutSection } from './sections/AboutSection'
import { ChallengesAndStakesSection } from './sections/ChallengesAndStakesSection'
import { DataFoundationSection } from './sections/DataFoundationSection'
import { ProcessSection } from './sections/ProcessSection'
import { ResearchAchievementsSection } from './sections/ResearchAchievementsSection'
import { DecisionSupportSection } from './sections/DecisionSupportSection'
import { FutureDirectionsSection } from './sections/FutureDirectionsSection'
import { GridExplorerPromoSection } from './sections/GridExplorerPromoSection'

export function HomePage() {
  return (
    <div className="home-glass-canvas">
      <div className="ambient-orb ambient-orb--one" aria-hidden="true" />
      <div className="ambient-orb ambient-orb--two" aria-hidden="true" />
      <div className="ambient-orb ambient-orb--three" aria-hidden="true" />

      <HeroSection />
      <AboutSection />
      <ChallengesAndStakesSection />
      <DataFoundationSection />
      <ProcessSection />
      <ResearchAchievementsSection />
      <DecisionSupportSection />
      <FutureDirectionsSection />
      <GridExplorerPromoSection />
    </div>
  )
}

export default HomePage