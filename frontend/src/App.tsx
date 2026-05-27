import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { BillboardPage } from '@/pages/BillboardPage'
import { TrackDetailPage } from '@/pages/TrackDetailPage'
import { ArtistDetailPage } from '@/pages/ArtistDetailPage'
import { AlbumDetailPage } from '@/pages/AlbumDetailPage'
import { NumberOnesPage } from '@/pages/NumberOnesPage'
import { AllTimeChartsPage } from '@/pages/AllTimeChartsPage'
import { RecordsPage } from '@/pages/RecordsPage'
import { SettingsPage } from '@/pages/SettingsPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/billboard" element={<BillboardPage />} />
          <Route path="/billboard/track/:trackId" element={<TrackDetailPage />} />
          <Route path="/billboard/artist/:artistName" element={<ArtistDetailPage />} />
          <Route path="/billboard/album/:albumName" element={<AlbumDetailPage />} />
          <Route path="/billboard/number-ones" element={<NumberOnesPage />} />
          <Route path="/billboard/all-time" element={<AllTimeChartsPage />} />
          <Route path="/billboard/records" element={<RecordsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
