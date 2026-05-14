import { useState, useEffect, useRef } from 'react'
import { getAgentLogs, clearAgentLogs } from '../../api/client'
import type { AgentLogEntry } from '../../types'

const typeColor: Record<string, string> = {
  start: 'text-blue-400',
  tool_call: 'text-yellow-400',
  tool_result: 'text-slate-300',
  end: 'text-green-400',
}

const typeBg: Record<string, string> = {
  start: 'bg-blue-900/30 border-blue-800/50',
  tool_call: 'bg-yellow-900/20 border-yellow-800/30',
  tool_result: 'bg-slate-800/60 border-slate-700/50',
  end: 'bg-green-900/20 border-green-800/30',
}

interface LogRowProps {
  entry: AgentLogEntry
}

function LogRow({ entry }: LogRowProps) {
  const colorCls = entry.is_error ? 'text-red-400' : typeColor[entry.type] ?? 'text-slate-300'
  const bgCls = entry.is_error
    ? 'bg-red-900/20 border-red-800/30'
    : typeBg[entry.type] ?? 'bg-slate-800/50 border-slate-700/30'

  return (
    <div className={`flex gap-3 px-4 py-2.5 border-b ${bgCls} items-start`}>
      {/* Time */}
      <span className="text-xs text-slate-500 font-mono flex-shrink-0 mt-0.5 w-16">{entry.time}</span>

      {/* Icon */}
      <span className="text-base flex-shrink-0">{entry.icon}</span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-semibold ${colorCls}`}>{entry.label}</span>
          {entry.step != null && (
            <span className="text-xs text-slate-600">step {entry.step}</span>
          )}
          <span className="text-xs bg-slate-700/60 text-slate-400 px-1.5 py-0.5 rounded font-mono">
            {entry.agent}
          </span>
        </div>
        {entry.detail && (
          <p className="text-xs text-slate-400 mt-0.5 leading-relaxed break-words">{entry.detail}</p>
        )}
      </div>
    </div>
  )
}

export default function AgentLogs() {
  const [logs, setLogs] = useState<AgentLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [agentFilter, setAgentFilter] = useState('All')
  const [typeFilter, setTypeFilter] = useState('All')
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const fetchLogs = async () => {
    try {
      const data = await getAgentLogs(300)
      setLogs(data.logs ?? [])
    } catch {
      // silently fail on polling errors
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [])

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchLogs, 2500)
      return () => clearInterval(intervalRef.current!)
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [autoRefresh])

  useEffect(() => {
    if (autoRefresh) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoRefresh])

  const handleClear = async () => {
    if (!confirm('Clear all agent logs?')) return
    await clearAgentLogs()
    setLogs([])
  }

  const agents = ['All', ...Array.from(new Set(logs.map((l) => l.agent))).sort()]
  const types = ['All', 'start', 'tool_call', 'tool_result', 'end']

  const filtered = logs.filter((l) => {
    const matchAgent = agentFilter === 'All' || l.agent === agentFilter
    const matchType = typeFilter === 'All' || l.type === typeFilter
    return matchAgent && matchType
  })

  const selectCls =
    'bg-slate-800 border border-slate-700 text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-blue-500'

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex-shrink-0 flex flex-wrap items-center gap-3 px-4 py-3 border-b border-slate-800 bg-slate-900/50">
        <h2 className="text-sm font-semibold text-slate-200 mr-2">Agent Logs</h2>

        {/* Filters */}
        <select value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)} className={selectCls}>
          {agents.map((a) => (
            <option key={a} value={a}>{a === 'All' ? 'All Agents' : a}</option>
          ))}
        </select>

        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className={selectCls}>
          {types.map((t) => (
            <option key={t} value={t}>{t === 'All' ? 'All Types' : t}</option>
          ))}
        </select>

        <div className="flex-1" />

        {/* Count */}
        <span className="text-xs text-slate-500">
          {filtered.length} / {logs.length} entries
        </span>

        {/* Auto-refresh */}
        <label className="flex items-center gap-2 cursor-pointer">
          <div
            onClick={() => setAutoRefresh((v) => !v)}
            className={`w-9 h-5 rounded-full transition-colors relative cursor-pointer ${
              autoRefresh ? 'bg-blue-600' : 'bg-slate-700'
            }`}
          >
            <span
              className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                autoRefresh ? 'translate-x-4' : 'translate-x-0.5'
              }`}
            />
          </div>
          <span className="text-xs text-slate-400">Live</span>
        </label>

        {/* Refresh */}
        <button
          onClick={fetchLogs}
          className="text-xs text-slate-400 hover:text-slate-200 transition-colors px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded-lg"
        >
          Refresh
        </button>

        {/* Clear */}
        {logs.length > 0 && (
          <button
            onClick={handleClear}
            className="text-xs text-red-400 hover:text-red-300 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Log list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-blue-500" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-600 text-sm gap-2">
            <span className="text-3xl">🤖</span>
            <p>No agent activity yet.</p>
            <p className="text-xs">Logs appear here when agents run (upload, study coach, validation…)</p>
          </div>
        ) : (
          <>
            {filtered.map((entry, i) => (
              <LogRow key={i} entry={entry} />
            ))}
            <div ref={bottomRef} />
          </>
        )}
      </div>
    </div>
  )
}
