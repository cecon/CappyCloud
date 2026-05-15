import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken } from './api'
import { AppLayout } from './components/AppLayout'
import { ThinkingIndicator } from './components/ThinkingIndicator'

const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage').then(m => ({ default: m.AnalyticsPage })))
const SkillsPage = lazy(() => import('./pages/SkillsPage').then(m => ({ default: m.SkillsPage })))
const ChatPage = lazy(() => import('./pages/ChatPage').then(m => ({ default: m.ChatPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('./pages/RegisterPage').then(m => ({ default: m.RegisterPage })))
const RunsPage = lazy(() => import('./pages/RunsPage').then(m => ({ default: m.RunsPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })))
const McpPage = lazy(() => import('./pages/McpPage').then(m => ({ default: m.McpPage })))

function PageLoader() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
      <ThinkingIndicator />
    </div>
  )
}

function ProtectedPage({ children }: { children: ReactNode }) {
  const token = getToken()
  return token ? <AppLayout>{children}</AppLayout> : <Navigate to="/login" replace />
}

export default function App() {
  const token = getToken()

  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedPage><DashboardPage /></ProtectedPage>
          }
        />
        <Route
          path="/chat"
          element={
            <ProtectedPage><ChatPage /></ProtectedPage>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedPage><SettingsPage /></ProtectedPage>
          }
        />
        <Route
          path="/skills"
          element={
            <ProtectedPage><SkillsPage /></ProtectedPage>
          }
        />
        <Route
          path="/runs"
          element={
            <ProtectedPage><RunsPage /></ProtectedPage>
          }
        />
        <Route
          path="/mcp"
          element={
            <ProtectedPage><McpPage /></ProtectedPage>
          }
        />
        <Route
          path="/analytics"
          element={
            <ProtectedPage><AnalyticsPage /></ProtectedPage>
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
