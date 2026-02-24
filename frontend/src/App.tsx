import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './useAuth'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Issues from './pages/Issues'
import IssueWriter from './pages/IssueWriter'
import Problems from './pages/Problems'
import Layout from './Layout'

function Protected({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth()
  if (loading) return <div className="flex min-h-screen items-center justify-center">Загрузка...</div>
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="issues" element={<Issues />} />
        <Route path="issues/new" element={<IssueWriter />} />
        <Route path="problems" element={<Problems />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
