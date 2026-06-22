import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AlbumEnrichmentView } from '@/components/shared/AlbumEnrichmentView'
import { AlbumEnrichmentSection } from '@/features/music/details/AlbumEnrichmentSection'
import type { StructuredAlbum } from '@/types/billboard'

function makeStructuredAlbum(overrides: Partial<StructuredAlbum> = {}): StructuredAlbum {
  return {
    summary: '',
    key_facts: [],
    genres: [],
    chart_performance: [],
    accolades: [],
    singles: [{ name: 'Lead Single', peak: 1, certification: 'Gold' }],
    ...overrides,
  }
}

describe('AlbumEnrichmentView', () => {
  it('renders cover art for structured lead singles when available', () => {
    const { container } = render(
      <AlbumEnrichmentView
        data={makeStructuredAlbum()}
        singleCoverUrls={{ 'lead single': '/covers/albums/42.jpg' }}
      />,
    )

    const img = container.querySelector('img')
    expect(img).toBeInTheDocument()
    expect(img?.getAttribute('src')).toBe('/covers/albums/42.jpg')
  })

  it('maps album detail track covers onto structured lead singles', () => {
    const { container } = render(
      <AlbumEnrichmentSection
        data={{
          tracks: [
            {
              track_name: "Is It Over Now? (Taylor's Version) (From The Vault)",
              cover_url: '/covers/albums/728.jpg',
            },
          ],
        } as any}
        enrichment={{
          wiki: {
            url: 'https://example.test/album',
            structured: makeStructuredAlbum({
              singles: [{ name: '"Is It Over Now?"', peak: 1 }],
            }),
          },
        } as any}
        releaseCycle={null}
      />,
    )

    const img = container.querySelector('img')
    expect(img).toBeInTheDocument()
    expect(img?.getAttribute('src')).toBe('/covers/albums/728.jpg')
  })
})
