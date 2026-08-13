import { Link } from 'react-router-dom'
import { ArrowDown, Disc3 } from 'lucide-react'

import type { ArchiveFeaturedItem, ArchiveOverview } from '@/types/accountArchive'
import { formatArchiveNumber } from '@/features/account-archive/model/archiveModel'

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
  return (
    <section id="archive-cover" className="archive-cover" data-archive-section="cover">
      <div className="archive-cover-copy">
        <h1>音乐档案</h1>

        <div className="archive-cover-facts" aria-label="档案概览">
          <div><strong>{formatArchiveNumber(overview.counts.saved_tracks)}</strong><span>收藏歌曲</span></div>
          <div><strong>{formatArchiveNumber(overview.counts.saved_albums)}</strong><span>收藏专辑</span></div>
          <div><strong>{formatArchiveNumber(overview.counts.saved_artists)}</strong><span>收藏艺人</span></div>
          <div><strong>{formatArchiveNumber(overview.counts.playlists)}</strong><span>歌单</span></div>
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
