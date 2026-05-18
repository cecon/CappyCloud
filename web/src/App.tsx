import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken } from './api'
import { AppLayout } from './components/AppLayout'
import { RequireAdmin } from './components/RequireAdmin'
import { ThinkingIndicator } from './components/ThinkingIndicator'

const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage').then(m => ({ default: m.AnalyticsPage })))
const SkillsPage = lazy(() => import('./pages/SkillsPage').then(m => ({ default: m.SkillsPage })))
const ChatPage = lazy(() => import('./pages/ChatPage').then(m => ({ default: m.ChatPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })))
const RunsPage = lazy(() => import('./pages/RunsPage').then(m => ({ default: m.RunsPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })))
const AdminUsersPage = lazy(() =>
  import('./pages/AdminUsersPage').then((m) => ({ default: m.AdminUsersPage })),
)
const AdminSandboxesPage = lazy(() =>
  import('./pages/AdminSandboxesPage').then((m) => ({ default: m.AdminSandboxesPage })),
)
const AdminProvidersPage = lazy(() =>
  import('./pages/AdminProvidersPage').then((m) => ({ default: m.AdminProvidersPage })),
)
const AdminModelsPage = lazy(() =>
  import('./pages/AdminModelsPage').then((m) => ({ default: m.AdminModelsPage })),
)
const AdminRepositoriesPage = lazy(() =>
  import('./pages/AdminRepositoriesPage').then((m) => ({ default: m.AdminRepositoriesPage })),
)

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

function AdminPage({ children }: { children: ReactNode }) {
  return (
    <ProtectedPage>
      <RequireAdmin>{children}</RequireAdmin>
    </ProtectedPage>
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
        <Route path="/mcp" element={<Navigate to="/admin/sandboxes" replace />} />
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
        <Route path="/register" element={<Navigate to="/login" replace />} />
        <Route path="/environments" element={<Navigate to="/" replace />} />
        <Route
          path="/admin/users"
          element={
            <AdminPage>
              <AdminUsersPage />
            </AdminPage>
          }
        />
        <Route
          path="/admin/sandboxes"
          element={
            <AdminPage>
              <AdminSandboxesPage />
            </AdminPage>
          }
        />
        <Route
          path="/admin/repositories"
          element={
            <AdminPage>
              <AdminRepositoriesPage />
            </AdminPage>
          }
        />
        <Route
          path="/admin/skills-global"
          element={<Navigate to="/admin/sandboxes" replace />}
        />
        <Route
          path="/admin/agents-global"
          element={<Navigate to="/admin/sandboxes" replace />}
        />
        <Route
          path="/admin/models"
          element={
            <AdminPage>
              <AdminModelsPage />
            </AdminPage>
          }
        />
        <Route
          path="/admin/providers"
          element={
            <AdminPage>
              <AdminProvidersPage />
            </AdminPage>
          }
        />
      </Routes>
    </Suspense>
  )
}
