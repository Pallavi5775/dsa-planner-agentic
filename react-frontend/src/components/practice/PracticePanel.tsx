import { useState, useEffect } from 'react'
import { addLog, updateNotes } from '../../api/client'
import type { Question } from '../../types'
import HintChat from '../chat/HintChat'

type Tab = 'log' | 'chat' | 'notes'

interface Props {
  question: Question | null
  initialTab: Tab
  isOpen: boolean
  onClose: () => void
  onSessionLogged: () => void
  onQuestionUpdated: (q: Question) => void
}

const TIMER_OPTIONS = [5, 10, 15, 20, 30, 45, 60]

function TabBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
        active
          ? 'border-blue-500 text-blue-400'
          : 'border-transparent text-slate-400 hover:text-slate-200'
      }`}
    >
      {label}
    </button>
  )
}

function LogSessionTab({
  question,
  onLogged,
}: {
  question: Question
  onLogged: () => void
}) {
  const [code, setCode] = useState('')
  const [logic, setLogic] = useState('')
  const [timeMins, setTimeMins] = useState(15)
  const [correct, setCorrect] = useState(true)
  const [hintUsed, setHintUsed] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    const last = question.logs[question.logs.length - 1]
    if (last) {
      setCode(last.code ?? '')
      setLogic(last.logic ?? '')
    } else {
      setCode('')
      setLogic('')
    }
    setSubmitted(false)
    setCorrect(true)
    setHintUsed(false)
  }, [question.id])

  const handleSubmit = async () => {
    if (submitting) return
    setSubmitting(true)
    try {
      await addLog(question.id, {
        code,
        logic,
        time_taken: timeMins * 60,
        correct,
        hint_used: hintUsed,
      })
      setSubmitted(true)
      setTimeout(onLogged, 800)
    } catch (e: any) {
      alert(e.response?.data?.detail ?? 'Failed to save session')
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-3">
        <div className="w-12 h-12 rounded-full bg-green-900/60 border border-green-700 flex items-center justify-center">
          <span className="text-2xl">✓</span>
        </div>
        <p className="text-green-400 font-medium">Session logged!</p>
        <p className="text-slate-500 text-sm">AI validation running in background…</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-4 overflow-y-auto h-full">
      {/* Correct / Incorrect toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => setCorrect(true)}
          className={`flex-1 py-2 rounded-xl text-sm font-medium border transition-colors ${
            correct
              ? 'bg-green-900/60 border-green-600 text-green-300'
              : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600'
          }`}
        >
          ✓ Solved
        </button>
        <button
          onClick={() => setCorrect(false)}
          className={`flex-1 py-2 rounded-xl text-sm font-medium border transition-colors ${
            !correct
              ? 'bg-red-900/60 border-red-600 text-red-300'
              : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600'
          }`}
        >
          ✗ Struggled
        </button>
      </div>

      {/* Logic notes */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1.5">
          Your approach / logic
        </label>
        <textarea
          value={logic}
          onChange={(e) => setLogic(e.target.value)}
          placeholder="Describe your approach, key observations, edge cases…"
          rows={4}
          className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-xl px-3 py-2 resize-none focus:outline-none focus:border-blue-500 placeholder-slate-600 transition-colors"
        />
      </div>

      {/* Code */}
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1.5">
          Your code
        </label>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="Paste or type your solution here…"
          rows={8}
          className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded-xl px-3 py-2 resize-none focus:outline-none focus:border-blue-500 transition-colors code-area"
          spellCheck={false}
        />
      </div>

      {/* Time + hint row */}
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <label className="block text-xs font-medium text-slate-400 mb-1.5">Time spent</label>
          <div className="flex flex-wrap gap-1.5">
            {TIMER_OPTIONS.map((t) => (
              <button
                key={t}
                onClick={() => setTimeMins(t)}
                className={`px-2.5 py-1 text-xs rounded-lg border transition-colors ${
                  timeMins === t
                    ? 'bg-blue-600/30 border-blue-500 text-blue-300'
                    : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600'
                }`}
              >
                {t}m
              </button>
            ))}
          </div>
        </div>

        <label className="flex items-center gap-2 cursor-pointer mt-4">
          <input
            type="checkbox"
            checked={hintUsed}
            onChange={(e) => setHintUsed(e.target.checked)}
            className="w-4 h-4 accent-blue-500"
          />
          <span className="text-xs text-slate-400">Used hint</span>
        </label>
      </div>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={submitting}
        className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded-xl transition-colors text-sm"
      >
        {submitting ? 'Saving…' : 'Log Session'}
      </button>

      {/* Last attempt info */}
      {question.accuracy != null && (
        <div className="text-xs text-slate-500 text-center">
          Last accuracy: <span className="text-slate-300">{Math.round(question.accuracy)}%</span>
          {question.next_revision && (
            <> · Next revision: <span className="text-slate-300">{question.next_revision}</span></>
          )}
        </div>
      )}

      {question.suggestions && (
        <div className="bg-yellow-900/20 border border-yellow-800/50 rounded-xl p-3 text-xs text-yellow-300">
          <span className="font-medium text-yellow-200">AI Suggestions: </span>
          {question.suggestions}
        </div>
      )}
    </div>
  )
}

function NotesTab({
  question,
  onUpdated,
}: {
  question: Question
  onUpdated: (q: Question) => void
}) {
  const [notes, setNotes] = useState(question.notes ?? '')
  const [gapAnalysis, setGapAnalysis] = useState(question.my_gap_analysis ?? '')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setNotes(question.notes ?? '')
    setGapAnalysis(question.my_gap_analysis ?? '')
    setSaved(false)
  }, [question.id])

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await updateNotes(question.id, notes, gapAnalysis)
      onUpdated(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e: any) {
      alert(e.response?.data?.detail ?? 'Failed to save notes')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 p-4 overflow-y-auto h-full">
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1.5">Personal notes</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Your notes, patterns to remember, gotchas…"
          rows={6}
          className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-xl px-3 py-2 resize-none focus:outline-none focus:border-blue-500 placeholder-slate-600 transition-colors"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1.5">My gap analysis</label>
        <textarea
          value={gapAnalysis}
          onChange={(e) => setGapAnalysis(e.target.value)}
          placeholder="What did you struggle with? What gaps in understanding did you identify?"
          rows={4}
          className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-xl px-3 py-2 resize-none focus:outline-none focus:border-blue-500 placeholder-slate-600 transition-colors"
        />
      </div>

      {question.my_gap_analysis && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 text-xs text-slate-400">
          <p className="font-medium text-slate-300 mb-1">AI Gap Analysis</p>
          <p>{question.my_gap_analysis}</p>
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={saving}
        className={`py-2.5 font-medium rounded-xl transition-colors text-sm ${
          saved
            ? 'bg-green-700 text-green-200'
            : 'bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50'
        }`}
      >
        {saving ? 'Saving…' : saved ? '✓ Saved' : 'Save Notes'}
      </button>
    </div>
  )
}

export default function PracticePanel({
  question,
  initialTab,
  isOpen,
  onClose,
  onSessionLogged,
  onQuestionUpdated,
}: Props) {
  const [tab, setTab] = useState<Tab>(initialTab)

  useEffect(() => {
    setTab(initialTab)
  }, [initialTab, question?.id])

  return (
    <>
      {/* Backdrop (mobile) */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-30 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={`
          flex flex-col bg-slate-900 border-l border-slate-800
          fixed right-0 top-[57px] bottom-0 w-full sm:w-[480px] z-40
          transform transition-transform duration-250 ease-out
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}
        `}
      >
        {question && (
          <>
            {/* Header */}
            <div className="flex-shrink-0 px-4 py-3 border-b border-slate-800 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="text-base font-semibold text-slate-100 truncate" title={question.title}>
                  {question.title}
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  {question.pattern} · {question.category} ·{' '}
                  <span
                    className={
                      question.difficulty === 'Easy'
                        ? 'text-green-400'
                        : question.difficulty === 'Hard'
                        ? 'text-red-400'
                        : 'text-yellow-400'
                    }
                  >
                    {question.difficulty}
                  </span>
                </p>
              </div>
              <button
                onClick={onClose}
                className="flex-shrink-0 text-slate-500 hover:text-slate-200 transition-colors text-xl leading-none mt-0.5"
                aria-label="Close"
              >
                ×
              </button>
            </div>

            {/* Tabs */}
            <div className="flex-shrink-0 border-b border-slate-800 flex px-2">
              <TabBtn label="Log Session" active={tab === 'log'} onClick={() => setTab('log')} />
              <TabBtn label="Hint Chat" active={tab === 'chat'} onClick={() => setTab('chat')} />
              <TabBtn label="Notes" active={tab === 'notes'} onClick={() => setTab('notes')} />
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-hidden">
              {tab === 'log' && (
                <LogSessionTab question={question} onLogged={onSessionLogged} />
              )}
              {tab === 'chat' && <HintChat question={question} />}
              {tab === 'notes' && (
                <NotesTab question={question} onUpdated={onQuestionUpdated} />
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}
