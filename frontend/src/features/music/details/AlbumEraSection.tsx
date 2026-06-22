import type { AlbumDetailResponse, AlbumEnrichmentResponse, ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import type { AlbumVersionGroup } from '@/types/billboard'
import { AlbumEraOverviewSection } from './AlbumEraOverviewSection'
import { AlbumReleaseTimelineSection } from './AlbumReleaseTimelineSection'
import { AlbumReleaseCompositionSection } from './AlbumReleaseCompositionSection'
import { AlbumListeningMatrixSection } from './AlbumListeningMatrixSection'
import { AlbumReleaseOverflowSection } from './AlbumReleaseOverflowSection'
import { AlbumEnrichmentSection } from './AlbumEnrichmentSection'
import { AlbumPersonalStorySection } from './AlbumPersonalStorySection'
import { VersionGroupSection } from './VersionGroupSection'

type AlbumEraSectionProps = {
  data: AlbumDetailResponse
  enrichment: AlbumEnrichmentResponse | null
  releaseCycle: ReleaseCycleAlbumDetailResponse | null
  releaseCycleLoading: boolean
  releaseCycleError: string | null
  releaseGroup?: AlbumVersionGroup | null
}

export function AlbumEraSection({
  data,
  enrichment,
  releaseCycle,
  releaseCycleLoading,
  releaseCycleError,
  releaseGroup,
}: AlbumEraSectionProps) {
  const hasReleaseCycle = !!releaseCycle && !releaseCycle.error

  return (
    <div className="mb-8">
      {hasReleaseCycle && (
        <AlbumEraOverviewSection data={data} releaseCycle={releaseCycle} />
      )}

      {releaseGroup && releaseGroup.versions && releaseGroup.versions.length >= 2 && (
        <div className="mb-8">
          <h3 className="mb-4 font-serif text-xl font-semibold">版本对比</h3>
          <VersionGroupSection kind="album" data={releaseGroup} />
        </div>
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
