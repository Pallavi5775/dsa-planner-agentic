import { useState } from 'react'
import AgentLogs from '../components/admin/AgentLogs'
import AdminUpload from '../components/admin/AdminUpload'
import UserManagement from '../components/admin/UserManagement'

type Tab = 'logs' | 'upload' | 'users'

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'logs', label: 'Agent Logs', icon: '🤖' },
  { id: 'upload', label: 'Upload Questions', icon: '📤' },
  { id: 'users', label: 'Users', icon: '👥' },
]

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>('logs')

  return (
    <div className="flex flex-col h-[calc(100vh-57px)]">
      {/* Tab bar */}
      <div className="flex-shrink-0 bg-slate-900 border-b border-slate-800 px-4 flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-300'
            }`}
          >
            <span>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {tab === 'logs' && <AgentLogs />}
        {tab === 'upload' && (
          <div className="h-full overflow-y-auto">
            <AdminUpload />
          </div>
        )}
        {tab === 'users' && (
          <div className="h-full overflow-y-auto">
            <UserManagement />
          </div>
        )}
      </div>
    </div>
  )
}
