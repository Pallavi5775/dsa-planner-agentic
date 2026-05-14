import { useState, useEffect } from 'react'
import { getUsers, createUser, deleteUser } from '../../api/client'
import { useAuthStore } from '../../store/auth'
import type { AdminUser } from '../../types'

const providerBadge: Record<string, string> = {
  microsoft: 'bg-blue-900/50 text-blue-300 border border-blue-700/50',
  google: 'bg-red-900/50 text-red-300 border border-red-700/50',
  github: 'bg-slate-700 text-slate-300 border border-slate-600',
}

export default function UserManagement() {
  const { user: currentUser } = useAuthStore()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Create user form
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [role, setRole] = useState<'user' | 'admin'>('user')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  const fetchUsers = async () => {
    try {
      setLoading(true)
      const data = await getUsers()
      setUsers(data)
    } catch (e: any) {
      setError(e.response?.data?.detail ?? 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchUsers() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return
    setCreating(true)
    setCreateError('')
    try {
      await createUser({ email: email.trim(), username: username.trim() || undefined, role })
      setEmail('')
      setUsername('')
      setRole('user')
      fetchUsers()
    } catch (e: any) {
      setCreateError(e.response?.data?.detail ?? 'Failed to create user')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (u: AdminUser) => {
    if (!confirm(`Delete user "${u.username}" (${u.email})? This cannot be undone.`)) return
    try {
      await deleteUser(u.id)
      setUsers((prev) => prev.filter((x) => x.id !== u.id))
    } catch (e: any) {
      alert(e.response?.data?.detail ?? 'Failed to delete user')
    }
  }

  const inputCls =
    'bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-xl px-3 py-2 focus:outline-none focus:border-blue-500 placeholder-slate-600 transition-colors'

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <h2 className="text-base font-semibold text-slate-200">User Management</h2>

      {/* Create user form */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <h3 className="text-sm font-medium text-slate-300 mb-4">Pre-register a user</h3>
        <form onSubmit={handleCreate} className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs text-slate-500 mb-1">Email *</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              className={inputCls + ' w-full'}
            />
          </div>
          <div className="w-40">
            <label className="block text-xs text-slate-500 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="optional"
              className={inputCls + ' w-full'}
            />
          </div>
          <div className="w-32">
            <label className="block text-xs text-slate-500 mb-1">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as 'user' | 'admin')}
              className={inputCls + ' w-full'}
            >
              <option value="user">user</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={creating || !email.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-xl transition-colors"
          >
            {creating ? 'Creating…' : 'Create'}
          </button>
        </form>
        {createError && (
          <p className="text-red-400 text-xs mt-2">{createError}</p>
        )}
        <p className="text-xs text-slate-600 mt-3">
          Pre-registered users can log in via OAuth once their email matches an OAuth provider.
        </p>
      </div>

      {/* Users table */}
      {error ? (
        <p className="text-red-400 text-sm">{error}</p>
      ) : loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-blue-500" />
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-300">{users.length} users</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="px-4 py-2.5 text-xs font-medium text-slate-500 uppercase tracking-wide">Username</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-slate-500 uppercase tracking-wide">Email</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-slate-500 uppercase tracking-wide">Role</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-slate-500 uppercase tracking-wide">Provider</th>
                  <th className="px-4 py-2.5 text-xs font-medium text-slate-500 uppercase tracking-wide"></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isSelf = u.id === currentUser?.id
                  return (
                    <tr key={u.id} className="border-b border-slate-800 hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-3">
                        <span className="text-sm font-medium text-slate-200">{u.username}</span>
                        {isSelf && (
                          <span className="ml-2 text-xs bg-blue-900/50 text-blue-400 px-1.5 py-0.5 rounded">you</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-400">{u.email}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                            u.role === 'admin'
                              ? 'bg-purple-900/50 text-purple-300 border border-purple-700/50'
                              : 'bg-slate-700 text-slate-400'
                          }`}
                        >
                          {u.role}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {u.oauth_provider ? (
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              providerBadge[u.oauth_provider] ?? 'bg-slate-700 text-slate-400'
                            }`}
                          >
                            {u.oauth_provider}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-600">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {!isSelf && (
                          <button
                            onClick={() => handleDelete(u)}
                            className="text-xs text-slate-600 hover:text-red-400 transition-colors"
                          >
                            Delete
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
