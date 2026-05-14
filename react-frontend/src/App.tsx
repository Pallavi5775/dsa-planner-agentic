import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from './store/auth'
import LoginPage from './pages/LoginPage'
import AdminPage from './pages/AdminPage'
import AppShell from './components/layout/AppShell'
import QuestionsDashboard from './components/questions/QuestionsDashboard'

function AuthHandler() {
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    const tok = searchParams.get('tok')
    const usr = searchParams.get('usr')
    const uid = searchParams.get('uid')
    const rol = searchParams.get('rol')
    const authError = searchParams.get('auth_error')
    const msConnected = searchParams.get('microsoft_connected')

    if (authError) {
      alert(`Login failed: ${decodeURIComponent(authError)}`)
      navigate('/login', { replace: true })
      return
    }

    if (msConnected) {
      navigate('/', { replace: true })
      return
    }

    if (tok && usr && uid && rol) {
      setAuth(tok, {
        id: parseInt(uid),
        username: decodeURIComponent(usr),
        role: rol as 'admin' | 'user',
      })
      navigate('/', { replace: true })
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return null
}

function ProtectedLayout() {
  const { token } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  return <AppShell />
}

function AdminGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore()
  if (!user || user.role !== 'admin') return <Navigate to="/" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <>
      <AuthHandler />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<QuestionsDashboard />} />
          <Route
            path="/admin"
            element={
              <AdminGuard>
                <AdminPage />
              </AdminGuard>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
