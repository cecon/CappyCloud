import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken } from './api'
import { ThinkingIndicator } from './components/ThinkingIndicator'

const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage').then(m => ({ default: m.AnalyticsPage })))
const SkillsPage = lazy(() => import('./pages/SkillsPage').then(m => ({ default: m.SkillsPage })))
const ChatPage = lazy(() => import('./pages/ChatPage').then(m => ({ default: m.ChatPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('./pages/RegisterPage').then(m => ({ default: m.RegisterPage })))
const RunsPage = lazy(() => import('./pages/RunsPage').then(m => ({ default: m.RunsPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })))

function PageLoader() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
      <ThinkingIndicator />
    </div>
  )
}

export default function App() {
  const token = getToken()

  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route
          path="/"
          element={
            token ? <DashboardPage /> : <Navigate to="/login" replace />
          }
        />
        <Route
          path="/chat"
          element={
            token ? <ChatPage /> : <Navigate to="/login" replace />
          }
        />
        <Route
          path="/settings"
          element={
            token ? <SettingsPage /> : <Navigate to="/login" replace />
          }
        />
        <Route
          path="/skills"
          element={
            token ? <SkillsPage /> : <Navigate to="/login" replace />
          }
        />
        <Route
          path="/runs"
          element={
            token ? <RunsPage /> : <Navigate to="/login" replace />
          }
        />
        <Route
          path="/analytics"
          element={
            token ? <AnalyticsPage /> : <Navigate to="/login" replace />
          }
        />
        <Route
          path="/login"
          element={
            token ? (
              <Navigate to="/" replace />
            ) : (
              <LoginPage onLoggedIn={() => (window.location.href = '/')} />
            )
          }
        />
        <Route
          path="/register"
          element={
            token ? (
              <Navigate to="/" replace />
            ) : (
              <RegisterPage onLoggedIn={() => (window.location.href = '/')} />
            )
          }
        />
        <Route path="/environments" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
