import { Link } from 'react-router-dom'

import { MobilePageHeader, MobileRankList } from '@/components/mobile'
import { displayName } from '@/lib/chinese'
import { billboardDetailLink, primaryArtistName } from '@/lib/navigation'
import { cn } from '@/lib/utils'
import type { MobileEntityRowProps } from '@/components/mobile'
import {
  SUB_TABS,
  formatNumber,
  formatWeekStart,
  type NumberOnesComputed,
  type SubTabKey,
  type YearFilteredNumberOnes,
} from '@/features/billboard/number-ones/numberOnesData'

interface MobileNumberOnesProps {
  activeTab: SubTabKey
  onTabChange: (tab: SubTabKey) => void
  computed: NumberOnesComputed
  yearFiltered: YearFilteredNumberOnes
  availableYears: number[]
  selectedYear: number
  onYearChange: (year: number) => void
}

function timelineRows(tab: SubTabKey, filtered: YearFilteredNumberOnes): MobileEntityRowProps[] {
  if (tab === 'tracks') return filtered.tracks.map((entry) => ({
    entityType: 'track',
    title: displayName(entry.track_name),
    subtitle: displayName(entry.artist_name),
    coverUrl: entry.cover_url,
    metric: formatNumber(entry.play_count),
    metricLabel: '播放',
    facts: [
      { label: '周次', value: formatWeekStart(entry.billboard_week) },
      { label: '累计冠军', value: `${entry.running_peak_wks} 周` },
    ],
    to: billboardDetailLink(`/music/tracks/${entry.track_id}`),
  }))
  if (tab === 'albums') return filtered.albums.map((entry) => ({
    entityType: 'album',
    title: displayName(entry.album_name),
    subtitle: displayName(entry.artist_name),
    coverUrl: entry.cover_url,
    metric: formatNumber(entry.play_count),
    metricLabel: '播放',
    facts: [
      { label: '周次', value: formatWeekStart(entry.billboard_week) },
      { label: '累计冠军', value: `${entry.album_pk_wks} 周` },
    ],
    to: billboardDetailLink(`/music/albums/${encodeURIComponent(entry.album_name)}?artist=${encodeURIComponent(entry.artist_name)}`),
  }))
  return filtered.artists.map((entry) => ({
    entityType: 'artist',
    title: displayName(entry.artist_name),
    coverUrl: entry.cover_url,
    metric: formatNumber(entry.play_count),
    metricLabel: '播放',
    facts: [
      { label: '周次', value: formatWeekStart(entry.billboard_week) },
      { label: '累计冠军', value: `${entry.artist_pk_wks} 周` },
    ],
    to: billboardDetailLink(`/music/artists/${encodeURIComponent(entry.artist_name)}`),
  }))
}

function championRows(tab: SubTabKey, computed: NumberOnesComputed): MobileEntityRowProps[] {
  if (tab === 'tracks') return computed.trackNo1WeeksSorted.slice(0, 10).map((entry, index) => ({
    entityType: 'track', rank: index + 1, title: displayName(entry.track_name), subtitle: displayName(entry.artist_name),
    coverUrl: entry.cover_url, metric: `${entry.weeks_at_no1}`, metricLabel: '冠军周',
    facts: [{ label: '最长连冠', value: `${entry.longest_streak}周` }],
    to: billboardDetailLink(`/music/tracks/${entry.track_id}`),
  }))
  if (tab === 'albums') return computed.albumNo1WeeksSorted.slice(0, 10).map((entry, index) => ({
    entityType: 'album', rank: index + 1, title: displayName(entry.album_name), subtitle: displayName(entry.artist_name),
    coverUrl: entry.cover_url, metric: `${entry.weeks_at_no1}`, metricLabel: '冠军周',
    facts: [{ label: '最长连冠', value: `${entry.longest_streak}周` }],
    to: billboardDetailLink(`/music/albums/${encodeURIComponent(entry.album_name)}?artist=${encodeURIComponent(entry.artist_name)}`),
  }))
  return computed.artistNo1WeeksSorted.slice(0, 10).map((entry, index) => ({
    entityType: 'artist', rank: index + 1, title: displayName(entry.artist_name), coverUrl: entry.cover_url,
    metric: `${entry.weeks_at_no1}`, metricLabel: '冠军周',
    facts: [{ label: '最长连冠', value: `${entry.longest_streak}周` }],
    to: billboardDetailLink(`/music/artists/${encodeURIComponent(primaryArtistName(entry))}`),
  }))
}

export function MobileNumberOnes({
  activeTab,
  onTabChange,
  computed,
  yearFiltered,
  availableYears,
  selectedYear,
  onYearChange,
}: MobileNumberOnesProps) {
  const uniqueCount = activeTab === 'tracks' ? yearFiltered.uniqueTrackCount : activeTab === 'albums' ? yearFiltered.uniqueAlbumCount : yearFiltered.uniqueArtistCount
  const allTimeCount = activeTab === 'tracks' ? computed.trackNo1WeeksSorted.length : activeTab === 'albums' ? computed.albumNo1WeeksSorted.length : computed.artistNo1WeeksSorted.length
  const topWeeks = activeTab === 'tracks' ? computed.trackNo1WeeksSorted[0]?.weeks_at_no1 ?? 0 : activeTab === 'albums' ? computed.albumNo1WeeksSorted[0]?.weeks_at_no1 ?? 0 : computed.artistNo1WeeksSorted[0]?.weeks_at_no1 ?? 0
  const longest = activeTab === 'tracks' ? computed.trackLongest.streak : activeTab === 'albums' ? computed.albumLongest.streak : computed.artistLongest.streak

  return (
    <div className="mobile-m4-page" data-mobile-page="number-ones">
      <MobilePageHeader
        eyebrow="Chart / Number Ones"
        title="每周榜首"
        description="按年份沿时间线回看每周的个人 Billboard 冠军。"
      />

      <div className="mobile-segmented" role="group" aria-label="冠军榜类型">
        {SUB_TABS.map((tab) => (
          <button key={tab.key} type="button" className={cn(activeTab === tab.key && 'active')} onClick={() => onTabChange(tab.key)}>{tab.label}</button>
        ))}
      </div>

      <div className="mobile-year-chips" aria-label="选择冠军年份">
        {availableYears.map((year) => (
          <button key={year} type="button" className={cn(year === selectedYear && 'active')} aria-pressed={year === selectedYear} onClick={() => onYearChange(year)}>{year}</button>
        ))}
      </div>

      <dl className="mobile-billboard-summary">
        <div><dt>{selectedYear} 独特冠军</dt><dd>{uniqueCount}</dd></div>
        <div><dt>全时段冠军</dt><dd>{allTimeCount}</dd></div>
        <div><dt>最多冠军周</dt><dd>{topWeeks}</dd></div>
        <div><dt>最长连冠</dt><dd>{longest}</dd></div>
      </dl>

      <section className="mobile-number-one-timeline">
        <header><p>{selectedYear} / Timeline</p><h2>每周冠军时间线</h2></header>
        {timelineRows(activeTab, yearFiltered).map((row, index) => (
          <div className="mobile-number-one-event" key={`${row.title}:${index}`}>
            <span aria-hidden="true" />
            <Link to={row.to ?? '#'}>
              <strong>{row.title}</strong>
              {row.subtitle && <small>{row.subtitle}</small>}
              <em>{row.facts?.[0]?.value} · {row.metric} 次 · {row.facts?.[1]?.value}</em>
            </Link>
          </div>
        ))}
      </section>

      <MobileRankList eyebrow="All-time / Top 10" title="冠军周数排行" rows={championRows(activeTab, computed)} emptyTitle="暂无冠军数据" />
    </div>
  )
}
