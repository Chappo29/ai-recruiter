import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import Sidebar from './components/Sidebar'
import { ToastProvider } from './components/Toast'
import { AuthProvider } from './contexts/AuthContext'
import AcceptInvite from './pages/AcceptInvite'
import BotSettings from './pages/BotSettings'
import Candidates from './pages/Candidates'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Register from './pages/Register'
import Vacancies from './pages/Vacancies'
import VacancyDetail from './pages/VacancyDetail'

function Layout({ children }) {
  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <Sidebar />
      <div style={{ flex: 1, overflowY: 'auto' }}>{children}</div>
    </div>
  )
}

function AuthedLayout({ children }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <AuthProvider>
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/accept-invite" element={<AcceptInvite />} />
          <Route
            path="/dashboard"
            element={
              <AuthedLayout>
                <Dashboard />
              </AuthedLayout>
            }
          />
          <Route
            path="/vacancies"
            element={
              <AuthedLayout>
                <Vacancies />
              </AuthedLayout>
            }
          />
          <Route
            path="/vacancies/:id"
            element={
              <AuthedLayout>
                <VacancyDetail />
              </AuthedLayout>
            }
          />
          <Route
            path="/candidates"
            element={
              <AuthedLayout>
                <Candidates />
              </AuthedLayout>
            }
          />
          <Route
            path="/bot"
            element={
              <AuthedLayout>
                <BotSettings />
              </AuthedLayout>
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
    </AuthProvider>
  )
}
