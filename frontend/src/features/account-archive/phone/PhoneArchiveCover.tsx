import { ArrowDown, Disc3 } from 'lucide-react'
import { Link } from 'react-router-dom'

import {
  formatArchiveNumber,
} from '@/features/account-archive/model/archiveModel'
import type { ArchiveOverview } from '@/types/accountArchive'
import { displayName, useChineseTextVersion } from '@/lib/chinese'

const ROLES = {
  first_saved: '最早收藏',
  latest_saved: '最近收藏',
  oldest_release: '最早发行',
  newest_release: '最新发行',
}

export function PhoneArchiveCover({ overview }: { overview: ArchiveOverview }) {
  useChineseTextVersion()
  const featured = overview.featured_items.slice(0, 2)
  return (
    <section id="archive-cover" className="phone-archive-cover" data-archive-section="cover">
      <div className="phone-archive-cover-art" aria-label="收藏封面故事">
        <div className="phone-archive-record" aria-hidden="true" />
        {featured.map((item, index) => {
          const content = (
            <>
              <span>{item.cover_url ? <img src={item.cover_url} alt="" /> : <Disc3 />}</span>
              <small>{ROLES[item.role]}</small>
              <strong>{displayName(item.track_name)}</strong>
              <em>{displayName(item.artist_name)}</em>
            </>
          )
          return item.deep_link
            ? <Link key={item.role} to={item.deep_link} className={`phone-archive-sleeve phone-archive-sleeve-${index + 1}`}>{content}</Link>
            : <div key={item.role} className={`phone-archive-sleeve phone-archive-sleeve-${index + 1}`}>{content}</div>
        })}
      </div>
      <div className="phone-archive-cover-copy">
        <h1>音乐<br />档案</h1>
      </div>
      <div className="phone-archive-cover-facts" aria-label="档案概览">
        <div><strong>{formatArchiveNumber(overview.counts.saved_tracks)}</strong><span>收藏歌曲</span></div>
        <div><strong>{formatArchiveNumber(overview.counts.saved_albums)}</strong><span>收藏专辑</span></div>
        <div><strong>{formatArchiveNumber(overview.counts.saved_artists)}</strong><span>收藏艺人</span></div>
        <div><strong>{formatArchiveNumber(overview.counts.playlists)}</strong><span>歌单</span></div>
      </div>
      <button
        type="button"
        className="phone-archive-start"
        onClick={() => document.getElementById('archive-journey')?.scrollIntoView({ behavior: 'smooth' })}
      >开始翻阅 <ArrowDown /></button>
    </section>
  )
}
