import type { AlbumDetailResponse, AlbumEnrichmentResponse, ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import type { AiTaskEvent, AiTaskRun } from '@/types/ai-tasks'
import { AITaskProgress } from '@/features/ai-tasks/AITaskProgress'
import { AlbumEraOverviewSection } from './AlbumEraOverviewSection'
import { AlbumReleaseTimelineSection } from './AlbumReleaseTimelineSection'
import { AlbumReleaseCompositionSection } from './AlbumReleaseCompositionSection'
import { AlbumReleaseOverflowSection } from './AlbumReleaseOverflowSection'
import { AlbumEnrichmentSection } from './AlbumEnrichmentSection'

type AlbumEraSectionProps = {
  data: AlbumDetailResponse
  enrichment: AlbumEnrichmentResponse | null
  enrichmentLoading: boolean
  enrichmentTask: AiTaskRun | null
  enrichmentTaskEvents: AiTaskEvent[]
  releaseCycle: ReleaseCycleAlbumDetailResponse | null
  releaseCycleLoading: boolean
  releaseCycleError: string | null
}

export function AlbumEraSection({
  data,
  enrichment,
  enrichmentLoading,
  enrichmentTask,
  enrichmentTaskEvents,
  releaseCycle,
  releaseCycleLoading,
  releaseCycleError,
}: AlbumEraSectionProps) {
  const hasReleaseCycle = !!releaseCycle && !releaseCycle.error
  const showEnrichmentTaskProgress = !!enrichmentTask && enrichmentTask.status !== 'done'

  return (
    <div className="mb-8">
      {hasReleaseCycle && (
        <AlbumEraOverviewSection data={data} releaseCycle={releaseCycle} />
      )}

      <AlbumReleaseTimelineSection
        data={data}
        enrichment={enrichment}
        releaseCycle={releaseCycle}
        releaseCycleLoading={releaseCycleLoading}
        releaseCycleError={releaseCycleError}
      />

      {hasReleaseCycle && (
        <>
          <AlbumReleaseCompositionSection
            enrichment={enrichment}
            releaseCycle={releaseCycle}
          />
          <AlbumReleaseOverflowSection releaseCycle={releaseCycle} />
        </>
      )}

      {showEnrichmentTaskProgress && (
        <div className="mb-8">
          <AITaskProgress task={enrichmentTask} events={enrichmentTaskEvents} />
        </div>
      )}

      {!showEnrichmentTaskProgress && !enrichmentLoading && (
        <AlbumEnrichmentSection data={data} enrichment={enrichment} releaseCycle={releaseCycle} />
      )}
    </div>
  )
}
