import { Navigate, Route, Routes } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Chat from './pages/Chat'
import Dashboard from './pages/Dashboard'
import KnowledgeBase from './pages/KnowledgeBase'
import Requests from './pages/Requests'
import Settings from './pages/Settings'
import TicketDetail from './pages/TicketDetail'
import Tickets from './pages/Tickets'

export default function App() {
  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-x-hidden md:pl-64">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/tickets" element={<Tickets />} />
          <Route path="/tickets/:ticketId" element={<TicketDetail />} />
          <Route path="/requests" element={<Requests />} />
          <Route path="/knowledge-base" element={<KnowledgeBase />} />
          <Route path="/settings" element={<Settings />} />
          <Route
            path="*"
            element={
              <div className="p-10 text-slate-500">
                Page not found. <a className="text-brand-600 underline" href="/dashboard">Back to dashboard</a>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  )
}
