import { Navigate, Route, Routes } from 'react-router-dom'

import LoadingPage from './pages/LoadingPage'
import ReportPage from './pages/ReportPage'
import SearchPage from './pages/SearchPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SearchPage />} />
      <Route path="/loading/:patientId" element={<LoadingPage />} />
      <Route path="/report/:sessionId" element={<ReportPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
