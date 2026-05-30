import type { CollectionInsights } from '@/types/account'
import { PersonalityHero } from '@/features/account/collection/components/PersonalityHero'
import { CollectionOverviewBlock } from '@/features/account/collection/components/CollectionOverviewBlock'
import { FirstSaveStoryBlock } from '@/features/account/collection/components/FirstSaveStoryBlock'
import { SaveLifecycleBlock } from '@/features/account/collection/components/SaveLifecycleBlock'
import { ChemistryBlock } from '@/features/account/collection/components/ChemistryBlock'
import { FlipSideAndMigrationBlock } from '@/features/account/collection/components/FlipSideAndMigrationBlock'
import { LeaderboardBlock } from '@/features/account/collection/components/LeaderboardBlock'
import { SavedTracksBrowser } from '@/features/account/collection/components/SavedTracksBrowser'
import { PlaylistsBrowser } from '@/features/account/collection/components/PlaylistsBrowser'
import { NotAvailable } from '@/features/account/collection/components/NotAvailable'

export function CollectionTab({ insights }: { insights: CollectionInsights }) {
  if (!insights.available || insights.empty) {
    return (
      <div className="space-y-6">
        <h2 className="font-serif text-3xl font-bold tracking-tight">
          你的收藏
        </h2>
        <NotAvailable />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <h2 className="font-serif text-3xl font-bold tracking-tight">
        你的收藏
      </h2>

      <PersonalityHero insights={insights} />
      <CollectionOverviewBlock insights={insights} />
      <FirstSaveStoryBlock insights={insights} />
      <SaveLifecycleBlock insights={insights} />
      <ChemistryBlock insights={insights} />
      <FlipSideAndMigrationBlock insights={insights} />
      <LeaderboardBlock insights={insights} />

      <section className="space-y-4">
        <h2 className="mb-5 font-serif text-xl font-semibold">浏览器</h2>
        <div className="grid grid-cols-1 gap-6">
          <SavedTracksBrowser />
          <PlaylistsBrowser />
        </div>
      </section>
    </div>
  )
}
