import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigationType, useParams } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'

const DashboardPage = lazy(() => import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const BillboardPage = lazy(() => import('@/pages/BillboardPage').then((m) => ({ default: m.BillboardPage })))
const TrackDetailPage = lazy(() => import('@/pages/TrackDetailPage').then((m) => ({ default: m.TrackDetailPage })))
const ArtistDetailPage = lazy(() => import('@/pages/ArtistDetailPage').then((m) => ({ default: m.ArtistDetailPage })))
const AlbumDetailPage = lazy(() => import('@/pages/AlbumDetailPage').then((m) => ({ default: m.AlbumDetailPage })))
const NumberOnesPage = lazy(() => import('@/pages/NumberOnesPage').then((m) => ({ default: m.NumberOnesPage })))
const AllTimeChartsPage = lazy(() => import('@/pages/AllTimeChartsPage').then((m) => ({ default: m.AllTimeChartsPage })))
const BillboardYearEndPage = lazy(() => import('@/pages/BillboardYearEndPage').then((m) => ({ default: m.BillboardYearEndPage })))
const RecordsPage = lazy(() => import('@/pages/RecordsPage').then((m) => ({ default: m.RecordsPage })))
const BillboardVersusPage = lazy(() => import('@/pages/BillboardVersusPage').then((m) => ({ default: m.BillboardVersusPage })))
const CommunityPage = lazy(() => import('@/pages/CommunityPage').then((m) => ({ default: m.CommunityPage })))
const CommunityAccountPage = lazy(() => import('@/pages/CommunityAccountPage').then((m) => ({ default: m.CommunityAccountPage })))
const PostDetailPage = lazy(() => import('@/pages/PostDetailPage').then((m) => ({ default: m.PostDetailPage })))
const AiInsightsPage = lazy(() => import('@/pages/AiInsightsPage').then((m) => ({ default: m.AiInsightsPage })))
const SettingsPage = lazy(() => import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const YearlyReviewPage = lazy(() => import('@/pages/YearlyReviewPage').then((m) => ({ default: m.YearlyReviewPage })))
const AccountCenterPage = lazy(() => import('@/pages/AccountCenterPage').then((m) => ({ default: m.AccountCenterPage })))
const AnalysisLayout = lazy(() => import('@/pages/AnalysisLayout').then((m) => ({ default: m.AnalysisLayout })))
const AnalysisStatsPage = lazy(() => import('@/pages/AnalysisStatsPage').then((m) => ({ default: m.AnalysisStatsPage })))
const AnalysisChartsPage = lazy(() => import('@/pages/AnalysisChartsPage').then((m) => ({ default: m.AnalysisChartsPage })))
const AnalysisRecordsPage = lazy(() => import('@/pages/AnalysisRecordsPage').then((m) => ({ default: m.AnalysisRecordsPage })))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage })))

function LegacyMusicRedirect({ kind }: { kind: 'track' | 'album' | 'artist' }) {
  const params = useParams()
  const location = useLocation()
  const value = kind === 'track' ? params.trackId : kind === 'album' ? params.albumName : params.artistName
  const plural = kind === 'track' ? 'tracks' : kind === 'album' ? 'albums' : 'artists'
  return <Navigate to={`/music/${plural}/${encodeURIComponent(value ?? '')}${location.search}`} replace />
}

function RouteFallback() {
  return (
    <div className="space-y-4 py-8">
      <div className="h-4 w-28 animate-pulse rounded bg-muted" />
      <div className="h-10 w-72 animate-pulse rounded bg-muted" />
      <div className="grid gap-4 md:grid-cols-3">
        <div className="h-32 animate-pulse rounded-lg bg-muted" />
        <div className="h-32 animate-pulse rounded-lg bg-muted" />
        <div className="h-32 animate-pulse rounded-lg bg-muted" />
      </div>
    </div>
  )
}

function ScrollToTop() {
  const { pathname } = useLocation()
  const navigationType = useNavigationType()
  useEffect(() => {
    if (navigationType !== 'POP') {
      window.scrollTo(0, 0)
    }
  }, [pathname, navigationType])
  return null
}

function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Suspense fallback={<RouteFallback />}><DashboardPage /></Suspense>} />
          <Route path="/billboard" element={<Suspense fallback={<RouteFallback />}><BillboardPage /></Suspense>} />
          <Route path="/music/tracks/:trackId" element={<Suspense fallback={<RouteFallback />}><TrackDetailPage /></Suspense>} />
          <Route path="/music/artists/:artistName" element={<Suspense fallback={<RouteFallback />}><ArtistDetailPage /></Suspense>} />
          <Route path="/music/albums/:albumName" element={<Suspense fallback={<RouteFallback />}><AlbumDetailPage /></Suspense>} />
          <Route path="/billboard/track/:trackId" element={<LegacyMusicRedirect kind="track" />} />
          <Route path="/billboard/artist/:artistName" element={<LegacyMusicRedirect kind="artist" />} />
          <Route path="/billboard/album/:albumName" element={<LegacyMusicRedirect kind="album" />} />
          <Route path="/billboard/number-ones" element={<Suspense fallback={<RouteFallback />}><NumberOnesPage /></Suspense>} />
          <Route path="/billboard/all-time" element={<Suspense fallback={<RouteFallback />}><AllTimeChartsPage /></Suspense>} />
          <Route path="/billboard/year-end" element={<Suspense fallback={<RouteFallback />}><BillboardYearEndPage /></Suspense>} />
          <Route path="/billboard/records" element={<Suspense fallback={<RouteFallback />}><RecordsPage /></Suspense>} />
          <Route path="/billboard/versus" element={<Suspense fallback={<RouteFallback />}><BillboardVersusPage /></Suspense>} />
          <Route path="/community" element={<Suspense fallback={<RouteFallback />}><CommunityPage /></Suspense>} />
          <Route path="/community/post/:postId" element={<Suspense fallback={<RouteFallback />}><PostDetailPage /></Suspense>} />
          <Route path="/community/account/:handle" element={<Suspense fallback={<RouteFallback />}><CommunityAccountPage /></Suspense>} />
          <Route path="/ai-insights" element={<Suspense fallback={<RouteFallback />}><AiInsightsPage /></Suspense>} />
          <Route path="/analysis/timeline" element={<Navigate to="/analysis/stats" replace />} />
          <Route path="/analysis/leaderboard" element={<Navigate to="/analysis/charts" replace />} />
          <Route path="/analysis/behavior" element={<Navigate to="/analysis/stats" replace />} />
          <Route path="/analysis/listening-hours" element={<Navigate to="/analysis/stats" replace />} />
          <Route path="/analysis/artists" element={<Navigate to="/analysis/charts?entity=artist" replace />} />
          <Route path="/analysis" element={<Suspense fallback={<RouteFallback />}><AnalysisLayout /></Suspense>}>
            <Route index element={<Navigate to="/analysis/stats" replace />} />
            <Route path="stats" element={<Suspense fallback={<RouteFallback />}><AnalysisStatsPage /></Suspense>} />
            <Route path="charts" element={<Suspense fallback={<RouteFallback />}><AnalysisChartsPage /></Suspense>} />
            <Route path="records" element={<Suspense fallback={<RouteFallback />}><AnalysisRecordsPage /></Suspense>} />
          </Route>
          <Route path="/settings" element={<Suspense fallback={<RouteFallback />}><SettingsPage /></Suspense>} />
          <Route path="/yearly-review" element={<Suspense fallback={<RouteFallback />}><YearlyReviewPage /></Suspense>} />
          <Route path="/account" element={<Suspense fallback={<RouteFallback />}><AccountCenterPage /></Suspense>} />
          <Route path="*" element={<Suspense fallback={<RouteFallback />}><NotFoundPage /></Suspense>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
