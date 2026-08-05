import { HeroSection } from './HeroSection'
import { PersonalityReveal } from './PersonalityReveal'
import { TopCharts } from './TopCharts'
import { GenrePanorama } from './GenrePanorama'
import { TimeStory } from './TimeStory'
import { DiscoveryReturns } from './DiscoveryReturns'
import { ListeningDepth } from './ListeningDepth'
import { SpecialMoments } from './SpecialMoments'
import { MonthlyDrilldown } from './MonthlyDrilldown'
import { YearComparison } from './YearComparison'
import { getPersonalityTheme } from '@/lib/personality-themes'
import type { WrappedFullResponse } from '@/types/yearly-review'
import { useViewportMode } from '@/hooks/useViewportMode'

interface CustomSummaryProps {
  data: WrappedFullResponse
}

export function CustomSummary({ data }: CustomSummaryProps) {
  const isPhone = useViewportMode() === 'phone'
  const theme = getPersonalityTheme(data.personality?.primary_label ?? '环球旅人')

  if (isPhone) {
    return (
      <div className="yearly-review-content">
        {data.hero && <section id="yearly-hero" className="mobile-story-section"><HeroSection hero={data.hero} theme={theme} lastYear={data.comparison?.last_year ?? null} /></section>}
        {data.top_lists && <section id="yearly-favorites" className="mobile-story-section"><TopCharts topLists={data.top_lists} /></section>}
        {(data.time_story || data.special_moments || data.monthly_drilldown.length > 0) && (
          <section id="yearly-time" className="mobile-story-section">
            {data.time_story && <TimeStory timeStory={data.time_story} />}
            {data.special_moments && <SpecialMoments specialMoments={data.special_moments} />}
            {data.monthly_drilldown.length > 0 && <MonthlyDrilldown monthlyDrilldown={data.monthly_drilldown} />}
          </section>
        )}
        <section id="yearly-taste" className="mobile-story-section"><GenrePanorama genrePanorama={data.genre_panorama} /></section>
        {data.discovery_returns && <section id="yearly-discovery" className="mobile-story-section"><DiscoveryReturns discovery={data.discovery_returns} /></section>}
        {data.listening_depth && <section id="yearly-depth" className="mobile-story-section"><ListeningDepth listeningDepth={data.listening_depth} /></section>}
        {data.personality && <section id="yearly-personality" className="mobile-story-section"><PersonalityReveal personality={data.personality} /></section>}
        {data.comparison && <section id="yearly-comparison" className="mobile-story-section"><YearComparison comparison={data.comparison} /></section>}
      </div>
    )
  }

  return (
    <div className="yearly-review-content">
      {data.hero && <section id="yearly-hero" className="mobile-story-section"><HeroSection hero={data.hero} theme={theme} lastYear={data.comparison?.last_year ?? null} /></section>}

      {data.personality && <section id="yearly-personality" className="mobile-story-section"><PersonalityReveal personality={data.personality} /></section>}

      {data.top_lists && <section id="yearly-favorites" className="mobile-story-section"><TopCharts topLists={data.top_lists} /></section>}

      <section id="yearly-taste" className="mobile-story-section"><GenrePanorama genrePanorama={data.genre_panorama} /></section>

      {data.time_story && <section id="yearly-time" className="mobile-story-section"><TimeStory timeStory={data.time_story} /></section>}

      {data.discovery_returns && <section id="yearly-discovery" className="mobile-story-section"><DiscoveryReturns discovery={data.discovery_returns} /></section>}

      {data.listening_depth && <section id="yearly-depth" className="mobile-story-section"><ListeningDepth listeningDepth={data.listening_depth} /></section>}

      {data.special_moments && <SpecialMoments specialMoments={data.special_moments} />}

      {data.monthly_drilldown.length > 0 && <MonthlyDrilldown monthlyDrilldown={data.monthly_drilldown} />}

      {data.comparison && <section id="yearly-comparison" className="mobile-story-section"><YearComparison comparison={data.comparison} /></section>}
    </div>
  )
}
