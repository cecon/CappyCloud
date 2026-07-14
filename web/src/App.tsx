import { lazy, Suspense, type ReactNode, useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { getToken, setToken } from './api'
import { AppLayout } from './components/AppLayout'
import { AdminOverlayRouter } from './components/admin/AdminOverlayRouter'
import { RequireAdmin } from './components/RequireAdmin'
import { RequireSuperAdmin } from './components/RequireSuperAdmin'
import { ThinkingIndicator } from './components/ThinkingIndicator'
import { useCurrentUser } from './hooks/useCurrentUser'

const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage').then(m => ({ default: m.AnalyticsPage })))
const SkillsPage = lazy(() => import('./pages/SkillsPage').then(m => ({ default: m.SkillsPage })))
const ChatPage = lazy(() => import('./pages/ChatPage').then(m => ({ default: m.ChatPage })))
const ChangePasswordPage = lazy(() =>
  import('./pages/ChangePasswordPage').then((m) => ({ default: m.ChangePasswordPage })),
)
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })))
const McpServerPage = lazy(() =>
  import('./pages/McpServerPage').then((m) => ({ default: m.McpServerPage })),
)
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
const AdminGlobalSkillsPage = lazy(() =>
  import('./pages/AdminGlobalSkillsPage').then((m) => ({ default: m.AdminGlobalSkillsPage })),
)

function PageLoader() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
      <ThinkingIndicator />
    </div>
  )
}

function ProtectedPage({ children }: { children: ReactNode }) {
  const location = useLocation()
  const state = useCurrentUser()

  useEffect(() => {
    if (state.status === 'error') {
      setToken(null)
    }
  }, [state.status])

  if (state.status === 'loading') {
    return <PageLoader />
  }

  if (state.status === 'anonymous') {
    return <Navigate to="/login" replace />
  }

  if (state.status === 'error') {
    return <Navigate to="/login" replace />
  }

  if (state.user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }

  return <AppLayout>{children}</AppLayout>
}

function AuthenticatedBarePage({ children }: { children: ReactNode }) {
  const token = getToken()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

function AdminPage({ children }: { children: ReactNode }) {
  return (
    <ProtectedPage>
      <RequireAdmin>
        <AdminOverlayRouter>{children}</AdminOverlayRouter>
      </RequireAdmin>
    </ProtectedPage>
  )
}

function SuperAdminPage({ children }: { children: ReactNode }) {
  return (
    <ProtectedPage>
      <RequireSuperAdmin>{children}</RequireSuperAdmin>
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
            <ProtectedPage><Navigate to="/chat" replace /></ProtectedPage>
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
            <SuperAdminPage>
              <SettingsPage />
            </SuperAdminPage>
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
            <ProtectedPage><McpServerPage /></ProtectedPage>
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
          path="/change-password"
          element={
            <AuthenticatedBarePage>
              <ChangePasswordPage />
            </AuthenticatedBarePage>
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
          element={
            <SuperAdminPage>
              <AdminOverlayRouter>
                <AdminGlobalSkillsPage />
              </AdminOverlayRouter>
            </SuperAdminPage>
          }
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
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </Suspense>
  )
}
