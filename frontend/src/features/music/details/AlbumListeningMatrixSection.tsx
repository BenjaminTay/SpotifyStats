import type { ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import { MatrixCell } from './AlbumDetailPrimitives'

type AlbumListeningMatrixSectionProps = {
  releaseCycle: ReleaseCycleAlbumDetailResponse
}

export function AlbumListeningMatrixSection({ releaseCycle }: AlbumListeningMatrixSectionProps) {
  if (!releaseCycle.track_matrix) {
    return null
  }

  const trackMatrix = releaseCycle.track_matrix
  const max = Math.max(...trackMatrix.data.flat(), 1)

  return (
    <div className="mb-8">
      <h3 className="mb-4 font-serif text-xl font-semibold">收听展开</h3>
      <GlassCard className="overflow-auto p-0">
        <table className="mx-6 my-0 min-w-full border-collapse">
          <thead>
            <tr>
              <th className="sticky left-0 bg-card pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                曲目
              </th>
              {trackMatrix.weeks.map((week) => (
                <th key={week} className="min-w-12 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  {week >= 0 ? `+${week}` : week}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trackMatrix.tracks.map((track, rowIndex) => (
              <tr key={track} className="transition-colors hover:bg-muted/40">
                <td className="sticky left-0 max-w-[220px] bg-card py-2 pr-4 font-sans text-[12px] font-semibold">
                  {displayName(track)}
                </td>
                {trackMatrix.data[rowIndex].map((value, colIndex) => (
                  <MatrixCell key={`${track}-${colIndex}`} value={value} max={max} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </GlassCard>
      <p className="mt-2 font-sans text-[11px] text-muted-foreground">数字为距发行周的周播放次数，横轴 0 为发行周。</p>
    </div>
  )
}
