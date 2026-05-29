import { HeroSection } from './HeroSection'
import { PersonalityReveal } from './PersonalityReveal'
import { TopCharts } from './TopCharts'
import { GenrePanorama } from './GenrePanorama'
import { TimeStory } from './TimeStory'
import { MusicMap } from './MusicMap'
import { DiscoveryReturns } from './DiscoveryReturns'
import { ListeningDepth } from './ListeningDepth'
import { SpecialMoments } from './SpecialMoments'
import { MonthlyDrilldown } from './MonthlyDrilldown'
import { YearComparison } from './YearComparison'
import { getPersonalityTheme } from '@/lib/personality-themes'
import type { WrappedFullResponse } from '@/types/yearly-review'

interface CustomSummaryProps {
  data: WrappedFullResponse
}

export function CustomSummary({ data }: CustomSummaryProps) {
  const theme = getPersonalityTheme(data.personality?.primary_label ?? '环球旅人')

  return (
    <div className="yearly-review-content">
      {data.hero && <HeroSection hero={data.hero} theme={theme} lastYear={data.comparison?.last_year ?? null} />}

      {data.personality && <PersonalityReveal personality={data.personality} />}

      {data.top_lists && <TopCharts topLists={data.top_lists} />}

      <GenrePanorama genrePanorama={data.genre_panorama} />

      {data.time_story && <TimeStory timeStory={data.time_story} />}

      <MusicMap musicMap={data.music_map} />

      {data.discovery_returns && <DiscoveryReturns discovery={data.discovery_returns} />}

      {data.listening_depth && <ListeningDepth listeningDepth={data.listening_depth} />}

      {data.special_moments && <SpecialMoments specialMoments={data.special_moments} />}

      {data.monthly_drilldown.length > 0 && <MonthlyDrilldown monthlyDrilldown={data.monthly_drilldown} />}

      {data.comparison && <YearComparison comparison={data.comparison} />}
    </div>
  )
}
