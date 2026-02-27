import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import Dashboard from './pages/Dashboard'
import Parse from './pages/Parse'
import Documents from './pages/Documents'
import Playground from './pages/Playground'
import Chat from './pages/Chat'
import Models from './pages/Models'
import Settings from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="parse" element={<Parse />} />
        <Route path="documents" element={<Documents />} />
        <Route path="playground" element={<Playground />} />
        <Route path="chat" element={<Chat />} />
        <Route path="models" element={<Models />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
