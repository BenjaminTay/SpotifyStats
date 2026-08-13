import { AlertCircle, Archive, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useArchiveOverview } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveNavigation } from '@/features/account-archive/hooks/useArchiveNavigation'
import { PhoneArchiveCover } from '@/features/account-archive/phone/PhoneArchiveCover'
import { PhoneArchiveNav } from '@/features/account-archive/phone/PhoneArchiveNav'
import { PhoneDiscoveryChapter } from '@/features/account-archive/phone/PhoneDiscoveryChapter'
import { PhoneJourneyChapter } from '@/features/account-archive/phone/PhoneJourneyChapter'
import { PhoneLibraryChapter } from '@/features/account-archive/phone/PhoneLibraryChapter'
import { PhoneOtherMediaChapter } from '@/features/account-archive/phone/PhoneOtherMediaChapter'
import { PhoneRelationshipsChapter } from '@/features/account-archive/phone/PhoneRelationshipsChapter'
import { PhoneReturnsChapter } from '@/features/account-archive/phone/PhoneReturnsChapter'
import { useRuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'

import '../phone/phoneArchive.css'

function PhoneArchiveState({ kind, onRetry }: { kind: 'loading' | 'error' | 'empty'; onRetry?: () => void }) {
  const { capabilities } = useRuntimeCapabilities()
  if (kind === 'loading') return <div className="phone-archive-page-state"><LoaderCircle className="animate-spin" /><p>正在打开口袋音乐档案</p></div>
  if (kind === 'error') return <div className="phone-archive-page-state"><AlertCircle /><h1>档案暂时无法打开</h1><p>请确认本地服务正在运行后重试。</p><button type="button" onClick={onRetry}>重新读取</button></div>
  return <div className="phone-archive-page-state"><Archive /><h1>档案柜还是空的</h1><p>导入 Spotify 账号数据后，可以浏览收藏、歌单与搜索档案。</p>{capabilities.imports && <Link to="/settings">前往设置导入</Link>}</div>
}

export function AccountArchivePhoneRoute() {
  const query = useArchiveOverview()
  const { activeSection, selectSection } = useArchiveNavigation(Boolean(query.data))
  if (query.isLoading) return <PhoneArchiveState kind="loading" />
  if (query.isError) return <PhoneArchiveState kind="error" onRetry={() => void query.refetch()} />
  if (!query.data || query.data.status === 'empty') return <PhoneArchiveState kind="empty" />
  return (
    <div className="phone-archive" data-account-presentation="phone-archive">
      <PhoneArchiveCover overview={query.data} />
      <PhoneArchiveNav activeSection={activeSection} onSelect={selectSection} />
      <main className="phone-archive-pages archive-pages">
        <PhoneJourneyChapter />
        <PhoneRelationshipsChapter />
        <PhoneReturnsChapter />
        <PhoneDiscoveryChapter />
        <PhoneLibraryChapter />
        <PhoneOtherMediaChapter />
      </main>
    </div>
  )
}
