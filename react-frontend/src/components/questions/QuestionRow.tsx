import type { Question } from '../../types'

interface Props {
  question: Question
  onPractice: (q: Question) => void
  onChat: (q: Question) => void
}

const difficultyColor: Record<string, string> = {
  Easy: 'bg-green-900/60 text-green-300 border border-green-700/50',
  Medium: 'bg-yellow-900/60 text-yellow-300 border border-yellow-700/50',
  Hard: 'bg-red-900/60 text-red-300 border border-red-700/50',
}

const coverageColor: Record<string, string> = {
  'Not Covered': 'bg-slate-800 text-slate-400',
  'In Progress': 'bg-blue-900/60 text-blue-300',
  Covered: 'bg-green-900/60 text-green-300',
}

function Badge({ text, cls }: { text: string; cls: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${cls}`}>
      {text}
    </span>
  )
}

function AccuracyBar({ value }: { value: number }) {
  const color = value >= 80 ? 'bg-green-500' : value >= 50 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="text-xs text-slate-300">{Math.round(value)}%</span>
    </div>
  )
}

export default function QuestionRow({ question: q, onPractice, onChat }: Props) {
  const isDue =
    q.next_revision && q.next_revision <= new Date().toISOString().slice(0, 10)

  return (
    <tr className="border-b border-slate-800 hover:bg-slate-800/50 transition-colors group">
      {/* Title */}
      <td className="px-4 py-3">
        <button
          onClick={() => onPractice(q)}
          className="text-sm text-slate-200 hover:text-blue-400 font-medium text-left transition-colors"
        >
          {q.title}
        </button>
        {q.logs.length > 0 && (
          <span className="ml-2 text-xs text-slate-500">{q.logs.length}×</span>
        )}
      </td>

      {/* Pattern */}
      <td className="px-4 py-3 hidden md:table-cell">
        <span className="text-xs text-slate-400">{q.pattern}</span>
      </td>

      {/* Difficulty */}
      <td className="px-4 py-3">
        <Badge
          text={q.difficulty}
          cls={difficultyColor[q.difficulty] ?? 'bg-slate-700 text-slate-300'}
        />
      </td>

      {/* Coverage */}
      <td className="px-4 py-3 hidden sm:table-cell">
        <Badge text={q.coverage_status} cls={coverageColor[q.coverage_status] ?? ''} />
      </td>

      {/* Next revision */}
      <td className="px-4 py-3 hidden lg:table-cell">
        {q.next_revision ? (
          <span className={`text-xs ${isDue ? 'text-red-400 font-medium' : 'text-slate-400'}`}>
            {isDue ? '⚡ Due' : q.next_revision}
          </span>
        ) : (
          <span className="text-xs text-slate-600">—</span>
        )}
      </td>

      {/* Accuracy */}
      <td className="px-4 py-3 hidden xl:table-cell">
        {q.accuracy != null ? (
          <AccuracyBar value={q.accuracy} />
        ) : (
          <span className="text-xs text-slate-600">—</span>
        )}
      </td>

      {/* Actions */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2 opacity-70 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => onPractice(q)}
            className="px-2.5 py-1 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors font-medium"
          >
            Practice
          </button>
          <button
            onClick={() => onChat(q)}
            className="px-2.5 py-1 text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg transition-colors"
          >
            Hint
          </button>
        </div>
      </td>
    </tr>
  )
}
