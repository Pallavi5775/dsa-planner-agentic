import type { QuestionFilters } from '../../types'

interface Props {
  filters: QuestionFilters
  patterns: string[]
  onFiltersChange: (f: QuestionFilters) => void
  totalShown: number
  totalAll: number
}

const selectCls =
  'bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 transition-colors'

const difficulties = ['All', 'Easy', 'Medium', 'Hard']
const coverages = ['All', 'Not Covered', 'In Progress', 'Covered']

export default function FilterBar({ filters, patterns, onFiltersChange, totalShown, totalAll }: Props) {
  const set = (patch: Partial<QuestionFilters>) => onFiltersChange({ ...filters, ...patch })

  const hasFilters =
    filters.search || filters.pattern !== 'All' || filters.difficulty !== 'All' || filters.coverage !== 'All'

  return (
    <div className="bg-slate-900 border-b border-slate-800 px-4 py-3 flex flex-wrap items-center gap-3">
      {/* Search */}
      <div className="flex-1 min-w-[180px]">
        <input
          type="text"
          placeholder="Search questions…"
          value={filters.search}
          onChange={(e) => set({ search: e.target.value })}
          className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder-slate-500 transition-colors"
        />
      </div>

      {/* Pattern */}
      <select
        value={filters.pattern}
        onChange={(e) => set({ pattern: e.target.value })}
        className={selectCls}
      >
        <option value="All">All Patterns</option>
        {patterns.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>

      {/* Difficulty */}
      <select
        value={filters.difficulty}
        onChange={(e) => set({ difficulty: e.target.value })}
        className={selectCls}
      >
        {difficulties.map((d) => (
          <option key={d} value={d}>
            {d === 'All' ? 'All Difficulties' : d}
          </option>
        ))}
      </select>

      {/* Coverage */}
      <select
        value={filters.coverage}
        onChange={(e) => set({ coverage: e.target.value })}
        className={selectCls}
      >
        {coverages.map((c) => (
          <option key={c} value={c}>
            {c === 'All' ? 'All Coverage' : c}
          </option>
        ))}
      </select>

      {/* Clear */}
      {hasFilters && (
        <button
          onClick={() => onFiltersChange({ search: '', pattern: 'All', difficulty: 'All', coverage: 'All' })}
          className="text-xs text-slate-400 hover:text-red-400 transition-colors whitespace-nowrap"
        >
          Clear filters
        </button>
      )}

      {/* Count */}
      <div className="ml-auto text-xs text-slate-500 whitespace-nowrap">
        {totalShown === totalAll ? `${totalAll} questions` : `${totalShown} / ${totalAll}`}
      </div>
    </div>
  )
}
