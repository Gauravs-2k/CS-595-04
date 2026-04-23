import { Navigate, Route, Routes } from 'react-router-dom'

import ErrorBoundary from './components/ErrorBoundary'
import LoadingPage from './pages/LoadingPage'
import ReportPage from './pages/ReportPage'
import SearchPage from './pages/SearchPage'
import UploadPage from './pages/UploadPage'

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/upload/:patientId" element={<UploadPage />} />
        <Route path="/loading/:patientId" element={<LoadingPage />} />
        <Route path="/report/:sessionId" element={<ReportPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}
