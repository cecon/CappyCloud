import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken } from './api'
import { ChatPage } from './pages/ChatPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'

/**
 * Rotas: login, registo ou chat autenticado.
 */
export default function App() {
  const token = getToken()

  return (
    <Routes>
      <Route
        path="/"
        element={
          token ? <ChatPage /> : <Navigate to="/login" replace />
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
    </Routes>
  )
}
