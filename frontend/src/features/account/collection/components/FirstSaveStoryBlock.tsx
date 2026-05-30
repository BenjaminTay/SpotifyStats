import { GlassCard } from '@/components/shared/GlassCard'
import type { CollectionInsights } from '@/types/account'
import { formatDate } from '@/features/account/collection/utils/formatDate'

export function FirstSaveStoryBlock({
  insights,
}: {
  insights: CollectionInsights
}) {
  const { first_save_story, archive_facts } = insights

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        第一首收藏的故事
      </h2>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <GlassCard className="border-l-2 border-accent-foreground p-8">
          {first_save_story ? (
            <div className="flex h-full flex-col justify-between space-y-6">
              <div className="space-y-3">
                <div className="flex items-start gap-4">
                  {first_save_story.cover_url && (
                    <img src={first_save_story.cover_url} alt={first_save_story.track_name}
                      className="h-16 w-16 flex-shrink-0 rounded-lg object-cover shadow-sm" />
                  )}
                  <div>
                    <p className="font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
                      {formatDate(first_save_story.save_date)}
                    </p>
                    <p className="font-serif text-lg leading-relaxed mt-1">
                      你收藏了{' '}
                      <span className="font-semibold">
                        {first_save_story.artist_name}
                      </span>{' '}
                      的《
                      <span className="font-semibold">
                        {first_save_story.track_name}
                      </span>
                  》，从此<span className="font-semibold">收藏夹</span>
                      的故事开始了。从那天算起，你一共播放了这首歌{' '}
                      <span className="font-semibold">
                        {first_save_story.total_plays}
                      </span>{' '}
                      次，平均每{' '}
                      <span className="font-semibold">
                        {first_save_story.avg_interval_days.toFixed(1)}
                      </span>{' '}
                      天就回来听一次。
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4 rounded-lg bg-muted/40 p-4">
                <div className="text-center">
                  <p className="font-serif text-2xl font-bold tabular-nums">
                    {first_save_story.days_since.toLocaleString()}
                  </p>
                  <p className="font-sans text-[11px] text-muted-foreground">
                    陪伴天数
                  </p>
                </div>
                <div className="text-center">
                  <p className="font-serif text-2xl font-bold tabular-nums">
                    {first_save_story.total_plays.toLocaleString()}
                  </p>
                  <p className="font-sans text-[11px] text-muted-foreground">
                    累计播放
                  </p>
                </div>
                <div className="text-center">
                  <p className="font-serif text-2xl font-bold tabular-nums">
                    {first_save_story.avg_interval_days.toFixed(1)}
                  </p>
                  <p className="font-sans text-[11px] text-muted-foreground">
                    平均间隔 (天)
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center py-12">
              <p className="font-sans text-sm text-muted-foreground">
                暂无第一首收藏的记录
              </p>
            </div>
          )}
        </GlassCard>

        <GlassCard className="p-8">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            收藏夹档案
          </p>
          <div className="space-y-6">
            <div>
              <p className="font-serif text-4xl font-bold leading-none tabular-nums">
                {archive_facts.total_duration_hrs.toLocaleString()}
              </p>
              <p className="mt-1 font-sans text-sm text-muted-foreground">
                总时长（小时）
              </p>
            </div>
            <div>
              <p className="font-serif text-4xl font-bold leading-none">
                {archive_facts.year_span ?? '--'}
              </p>
              <p className="mt-1 font-sans text-sm text-muted-foreground">
                年代跨度
              </p>
            </div>
            <div>
              {archive_facts.oldest_track ? (
                <>
                  <p className="font-serif text-xl font-semibold leading-tight">
                    {archive_facts.oldest_track.track_name}
                  </p>
                  <p className="mt-0.5 font-sans text-sm text-muted-foreground">
                    {archive_facts.oldest_track.artist_name} &middot;{' '}
                    {archive_facts.oldest_track.year}
                  </p>
                </>
              ) : (
                <p className="font-serif text-xl font-semibold leading-tight text-muted-foreground">
                  无
                </p>
              )}
              <p className="mt-0.5 font-sans text-xs text-muted-foreground">
                最老曲目
              </p>
            </div>
          </div>
        </GlassCard>
      </div>
    </section>
  )
}
