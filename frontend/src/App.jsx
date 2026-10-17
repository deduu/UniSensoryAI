import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import ProtectedRoute from './components/auth/ProtectedRoute'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import Login from './pages/Login'
import Models from './pages/Models'
import Settings from './pages/Settings'
import Paper from './pages/Paper'
import Documents from './pages/Documents'
import Parse from './pages/Parse'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="documents" element={<Documents />} />
          <Route path="uploads" element={<Parse />} />
          <Route path="chat" element={<Chat />} />
          <Route path="paper" element={<Paper />} />
          <Route path="models" element={<Models />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  )
}
