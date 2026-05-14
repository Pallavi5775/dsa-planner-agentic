import { useState, useEffect, useMemo } from 'react'
import { getQuestions } from '../../api/client'
import type { Question, QuestionFilters } from '../../types'
import FilterBar from './FilterBar'
import QuestionRow from './QuestionRow'
import PracticePanel from '../practice/PracticePanel'

const INIT_FILTERS: QuestionFilters = {
  search: '',
  pattern: 'All',
  difficulty: 'All',
  coverage: 'All',
}

type PanelTab = 'log' | 'chat' | 'notes'

function StatCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl px-5 py-4 flex-1 min-w-[120px]">
      <p className="text-2xl font-bold text-slate-100">{value}</p>
      <p className="text-sm text-slate-400 mt-0.5">{label}</p>
      {sub && <p className="text-xs text-slate-600 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function QuestionsDashboard() {
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState<QuestionFilters>(INIT_FILTERS)
  const [selectedQ, setSelectedQ] = useState<Question | null>(null)
  const [panelTab, setPanelTab] = useState<PanelTab>('log')

  const fetchQuestions = async () => {
    try {
      setLoading(true)
      const data = await getQuestions()
      setQuestions(data)
    } catch (e: any) {
      setError(e.response?.data?.detail ?? 'Failed to load questions')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchQuestions()
  }, [])

  const today = new Date().toISOString().slice(0, 10)

  const stats = useMemo(() => {
    const covered = questions.filter((q) => q.coverage_status === 'Covered').length
    const due = questions.filter((q) => q.next_revision && q.next_revision <= today).length
    const avgAcc = questions
      .filter((q) => q.accuracy != null)
      .map((q) => q.accuracy!)
    const acc = avgAcc.length ? Math.round(avgAcc.reduce((a, b) => a + b, 0) / avgAcc.length) : null
    return { covered, due, acc }
  }, [questions, today])

  const patterns = useMemo(
    () => Array.from(new Set(questions.map((q) => q.pattern))).sort(),
    [questions]
  )

  const filtered = useMemo(() => {
    return questions.filter((q) => {
      const matchSearch =
        !filters.search ||
        q.title.toLowerCase().includes(filters.search.toLowerCase()) ||
        q.pattern.toLowerCase().includes(filters.search.toLowerCase())
      const matchPattern = filters.pattern === 'All' || q.pattern === filters.pattern
      const matchDiff = filters.difficulty === 'All' || q.difficulty === filters.difficulty
      const matchCov = filters.coverage === 'All' || q.coverage_status === filters.coverage
      return matchSearch && matchPattern && matchDiff && matchCov
    })
  }, [questions, filters])

  const openPanel = (q: Question, tab: PanelTab = 'log') => {
    setSelectedQ(q)
    setPanelTab(tab)
  }

  const closePanel = () => setSelectedQ(null)

  const handleSessionLogged = () => {
    fetchQuestions()
    closePanel()
  }

  const handleQuestionUpdated = (updated: Question) => {
    setQuestions((prev) => prev.map((q) => (q.id === updated.id ? updated : q)))
    setSelectedQ(updated)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-blue-500" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-red-400 mb-3">{error}</p>
          <button
            onClick={fetchQuestions}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-57px)] overflow-hidden">
      {/* Main content */}
      <div className={`flex flex-col flex-1 overflow-hidden transition-all duration-300 ${selectedQ ? 'mr-0' : ''}`}>
        {/* Stats */}
        <div className="flex gap-3 p-4 overflow-x-auto">
          <StatCard label="Total questions" value={questions.length} />
          <StatCard label="Covered" value={stats.covered} sub={`${Math.round((stats.covered / (questions.length || 1)) * 100)}%`} />
          <StatCard label="Due for revision" value={stats.due} />
          {stats.acc != null && <StatCard label="Avg accuracy" value={`${stats.acc}%`} />}
        </div>

        {/* Filter bar */}
        <FilterBar
          filters={filters}
          patterns={patterns}
          onFiltersChange={setFilters}
          totalShown={filtered.length}
          totalAll={questions.length}
        />

        {/* Table */}
        <div className="flex-1 overflow-auto">
          {filtered.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-slate-500 text-sm">
              No questions match your filters.
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 bg-slate-950 border-b border-slate-800 z-10">
                <tr>
                  <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase tracking-wide">Title</th>
                  <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase tracking-wide hidden md:table-cell">Pattern</th>
                  <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase tracking-wide">Difficulty</th>
                  <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase tracking-wide hidden sm:table-cell">Coverage</th>
                  <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase tracking-wide hidden lg:table-cell">Next Due</th>
                  <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase tracking-wide hidden xl:table-cell">Accuracy</th>
                  <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase tracking-wide">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((q) => (
                  <QuestionRow
                    key={q.id}
                    question={q}
                    onPractice={(q) => openPanel(q, 'log')}
                    onChat={(q) => openPanel(q, 'chat')}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Practice Panel */}
      <PracticePanel
        question={selectedQ}
        initialTab={panelTab}
        isOpen={!!selectedQ}
        onClose={closePanel}
        onSessionLogged={handleSessionLogged}
        onQuestionUpdated={handleQuestionUpdated}
      />
    </div>
  )
}
