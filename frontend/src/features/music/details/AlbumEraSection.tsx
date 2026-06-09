import type { AlbumDetailResponse, AlbumEnrichmentResponse, ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import { AlbumEraOverviewSection } from './AlbumEraOverviewSection'
import { AlbumReleaseTimelineSection } from './AlbumReleaseTimelineSection'
import { AlbumReleaseCompositionSection } from './AlbumReleaseCompositionSection'
import { AlbumListeningMatrixSection } from './AlbumListeningMatrixSection'
import { AlbumReleaseOverflowSection } from './AlbumReleaseOverflowSection'
import { AlbumEnrichmentSection } from './AlbumEnrichmentSection'
import { AlbumPersonalStorySection } from './AlbumPersonalStorySection'

type AlbumEraSectionProps = {
  data: AlbumDetailResponse
  enrichment: AlbumEnrichmentResponse | null
  releaseCycle: ReleaseCycleAlbumDetailResponse | null
  releaseCycleLoading: boolean
  releaseCycleError: string | null
}

export function AlbumEraSection({
  data,
  enrichment,
  releaseCycle,
  releaseCycleLoading,
  releaseCycleError,
}: AlbumEraSectionProps) {
  const hasReleaseCycle = !!releaseCycle && !releaseCycle.error

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
          <AlbumListeningMatrixSection releaseCycle={releaseCycle} />
          <AlbumReleaseOverflowSection releaseCycle={releaseCycle} />
        </>
      )}

      <AlbumEnrichmentSection data={data} enrichment={enrichment} />
      <AlbumPersonalStorySection data={data} />
    </div>
  )
}
