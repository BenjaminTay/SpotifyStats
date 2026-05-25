import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { BillboardPage } from '@/pages/BillboardPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/billboard" element={<BillboardPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
