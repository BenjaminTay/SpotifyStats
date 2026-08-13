import { Link } from 'react-router-dom'
import { AlertCircle, Archive, LoaderCircle } from 'lucide-react'

import { AnalysisPageHeader } from '@/components/shared/AnalysisPageHeader'
import { AnalysisSubNav } from '@/components/shared/AnalysisSubNav'
import { ArchiveCover } from '@/features/account-archive/desktop/ArchiveCover'
import { ArchiveIndex } from '@/features/account-archive/desktop/ArchiveIndex'
import { CohortsSection } from '@/features/account-archive/desktop/CohortsSection'
import { DiscoverySection } from '@/features/account-archive/desktop/DiscoverySection'
import { JourneySection } from '@/features/account-archive/desktop/JourneySection'
import { LibrarySection } from '@/features/account-archive/desktop/LibrarySection'
import { OtherMediaSection } from '@/features/account-archive/desktop/OtherMediaSection'
import { ReturnsSection } from '@/features/account-archive/desktop/ReturnsSection'
import { useArchiveOverview } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveNavigation } from '@/features/account-archive/hooks/useArchiveNavigation'
import { useRuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'

import '../accountArchive.css'

function ArchivePageSkeleton() {
  return (
    <div className="archive-page archive-page-loading" aria-label="正在打开音乐档案">
      <div className="archive-loading-cover">
        <span />
        <span />
        <span />
      </div>
      <div className="archive-loading-line"><LoaderCircle className="animate-spin" />正在整理本地档案</div>
    </div>
  )
}

function ArchivePageError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="archive-page-state" role="alert">
      <AlertCircle aria-hidden="true" />
      <h1>档案暂时无法打开</h1>
      <p>请确认本地服务正在运行后重试。</p>
      <button type="button" onClick={onRetry}>重新读取</button>
    </div>
  )
}

function ArchiveEmptyState() {
  const { capabilities } = useRuntimeCapabilities()
  return (
    <div className="archive-page-state">
      <Archive aria-hidden="true" />
      <h1>档案柜还是空的</h1>
      <p>导入 Spotify 账号数据后，可以浏览收藏、歌单与搜索档案。</p>
      {capabilities.imports && <Link to="/settings">前往设置导入数据</Link>}
    </div>
  )
}

export function AccountArchiveDesktopRoute() {
  const query = useArchiveOverview()
  const { activeSection, selectSection } = useArchiveNavigation(Boolean(query.data))

  return (
    <>
      <AnalysisPageHeader />
      <AnalysisSubNav />
      {query.isLoading && <ArchivePageSkeleton />}
      {query.isError && <ArchivePageError onRetry={() => void query.refetch()} />}
      {query.data?.status === 'empty' && <ArchiveEmptyState />}
      {query.data && query.data.status !== 'empty' && (
        <main className="archive-page">
          <ArchiveCover overview={query.data} />
          <div className="archive-reader">
            <aside className="archive-index-column">
              <ArchiveIndex activeSection={activeSection} onSelect={selectSection} />
            </aside>
            <div className="archive-pages">
              <JourneySection />
              <CohortsSection />
              <ReturnsSection />
              <DiscoverySection />
              <LibrarySection />
              <OtherMediaSection />
            </div>
          </div>
        </main>
      )}
    </>
  )
}
