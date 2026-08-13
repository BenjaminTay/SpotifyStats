import { ArrowDown, Database, Disc3 } from 'lucide-react'
import { Link } from 'react-router-dom'

import {
  formatArchiveHours,
  formatArchiveMonth,
  formatArchiveNumber,
} from '@/features/account-archive/model/archiveModel'
import type { ArchiveOverview } from '@/types/accountArchive'

const ROLES = {
  first_saved: '最早收藏',
  latest_saved: '最近收藏',
  oldest_release: '最早发行',
  newest_release: '最新发行',
}

export function PhoneArchiveCover({ overview }: { overview: ArchiveOverview }) {
  const featured = overview.featured_items.slice(0, 2)
  return (
    <section id="archive-cover" className="phone-archive-cover" data-archive-section="cover">
      <div className="phone-archive-cover-topline">
        <span>POCKET MUSIC ARCHIVE</span>
        <span>NO. {overview.data_revision.slice(0, 6).toUpperCase()}</span>
      </div>
      <div className="phone-archive-cover-art" aria-label="收藏封面故事">
        <div className="phone-archive-record" aria-hidden="true" />
        {featured.map((item, index) => {
          const content = (
            <>
              <span>{item.cover_url ? <img src={item.cover_url} alt="" /> : <Disc3 />}</span>
              <small>{ROLES[item.role]}</small>
              <strong>{item.track_name}</strong>
              <em>{item.artist_name}</em>
            </>
          )
          return item.deep_link
            ? <Link key={item.role} to={item.deep_link} className={`phone-archive-sleeve phone-archive-sleeve-${index + 1}`}>{content}</Link>
            : <div key={item.role} className={`phone-archive-sleeve phone-archive-sleeve-${index + 1}`}>{content}</div>
        })}
      </div>
      <div className="phone-archive-cover-copy">
        <p>Personal music archive</p>
        <h1>音乐<br />档案</h1>
        <blockquote>哪些音乐只是路过，<br />哪些真正留了下来？</blockquote>
      </div>
      <div className="phone-archive-cover-facts" aria-label="档案概览">
        <div><strong>{formatArchiveNumber(overview.counts.saved_tracks)}</strong><span>首当前收藏</span></div>
        <div><strong>{formatArchiveNumber(overview.counts.playlists)}</strong><span>个歌单</span></div>
        <div><strong>{overview.coverage.saved_tracks_linked_to_history_pct.toFixed(1)}%</strong><span>可关联播放</span></div>
        <div><strong>{formatArchiveHours(overview.coverage.known_duration_ms)}</strong><span>收藏总时长</span></div>
      </div>
      <div className="phone-archive-cover-meta">
        <span><Database />{formatArchiveMonth(overview.period.first_saved_at)}—{formatArchiveMonth(overview.period.latest_saved_at)}</span>
        <Link to="/settings">数据状态</Link>
      </div>
      <button
        type="button"
        className="phone-archive-start"
        onClick={() => document.getElementById('archive-journey')?.scrollIntoView({ behavior: 'smooth' })}
      >开始翻阅 <ArrowDown /></button>
    </section>
  )
}
