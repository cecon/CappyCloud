import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken } from './api'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { SkillsPage } from './pages/SkillsPage'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { RunsPage } from './pages/RunsPage'
import { SettingsPage } from './pages/SettingsPage'

/**
 * Rotas: dashboard inicial, chat, login, registo e áreas autenticadas.
 */
export default function App() {
  const token = getToken()

  return (
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
  )
}
