import { Link } from 'react-router-dom'
import { ArrowDown, Database, Disc3 } from 'lucide-react'

import type { ArchiveFeaturedItem, ArchiveOverview } from '@/types/accountArchive'
import {
  formatArchiveHours,
  formatArchiveMonth,
  formatArchiveNumber,
} from '@/features/account-archive/model/archiveModel'

const ROLE_LABELS: Record<ArchiveFeaturedItem['role'], string> = {
  first_saved: '最早收藏',
  latest_saved: '最近收藏',
  oldest_release: '最早发行',
  newest_release: '最新发行',
}

function ArchiveSleeve({ item, index }: { item: ArchiveFeaturedItem; index: number }) {
  const content = (
    <>
      <span className="archive-sleeve-art">
        {item.cover_url ? <img src={item.cover_url} alt="" /> : <Disc3 aria-hidden="true" />}
      </span>
      <span className="archive-sleeve-caption">
        <small>{ROLE_LABELS[item.role]}</small>
        <strong>{item.track_name}</strong>
        <span>{item.artist_name}</span>
      </span>
    </>
  )
  return item.deep_link ? (
    <Link to={item.deep_link} className={`archive-sleeve archive-sleeve-${index + 1}`}>
      {content}
    </Link>
  ) : (
    <div className={`archive-sleeve archive-sleeve-${index + 1}`}>{content}</div>
  )
}

export function ArchiveCover({ overview }: { overview: ArchiveOverview }) {
  const period = `${formatArchiveMonth(overview.period.first_saved_at)}—${formatArchiveMonth(overview.period.latest_saved_at)}`
  return (
    <section id="archive-cover" className="archive-cover" data-archive-section="cover">
      <div className="archive-cover-copy">
        <div className="archive-cover-overline">
          <span>Personal Music Archive</span>
          <span>No. {overview.data_revision.slice(0, 6).toUpperCase()}</span>
        </div>
        <h1>音乐档案</h1>
        <p className="archive-cover-question">哪些音乐只是路过，哪些真正留了下来？</p>
        <p className="archive-cover-intro">
          一份关于收藏、回访与重新相遇的长期记录。这里不替你定义人格，只保存可以被数据证明的关系。
        </p>

        <div className="archive-cover-facts" aria-label="档案概览">
          <div><strong>{formatArchiveNumber(overview.counts.saved_tracks)}</strong><span>首当前收藏</span></div>
          <div><strong>{formatArchiveNumber(overview.counts.playlists)}</strong><span>个歌单</span></div>
          <div><strong>{overview.coverage.saved_tracks_linked_to_history_pct.toFixed(1)}%</strong><span>可关联播放</span></div>
          <div><strong>{formatArchiveHours(overview.coverage.known_duration_ms)}</strong><span>已知收藏时长</span></div>
        </div>

        <div className="archive-cover-footer">
          <span><Database aria-hidden="true" />收藏记录 {period}</span>
          <span>播放数据截至 {formatArchiveMonth(overview.period.latest_play_date)}</span>
          <Link to="/settings">查看数据状态</Link>
        </div>
      </div>

      <div className="archive-collage" aria-label="档案中的四个收藏故事">
        <div className="archive-collage-ring" aria-hidden="true" />
        {overview.featured_items.map((item, index) => (
          <ArchiveSleeve key={`${item.role}-${item.track_name}`} item={item} index={index} />
        ))}
        {overview.featured_items.length === 0 && (
          <div className="archive-collage-empty"><Disc3 aria-hidden="true" /><span>等待收藏封面</span></div>
        )}
      </div>

      <button
        type="button"
        className="archive-cover-scroll"
        onClick={() => document.getElementById('archive-journey')?.scrollIntoView({ behavior: 'smooth' })}
      >
        <ArrowDown aria-hidden="true" /> 开始翻阅
      </button>
    </section>
  )
}
