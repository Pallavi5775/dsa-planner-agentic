import { useState, useRef } from 'react'
import { uploadMd, uploadMdAgentic, syncQuestions } from '../../api/client'

interface TraceEntry {
  step: number
  tool: string
  input: Record<string, unknown>
  result_summary: string
  status?: string
  is_error?: boolean
}

interface UploadResult {
  added: { title: string; pattern: string; difficulty: string; hint?: string }[]
  skipped_duplicates: string[]
  total_added: number
  total_skipped: number
  summary: string
  trace?: TraceEntry[]
  total_tool_calls?: number
}

export default function AdminUpload() {
  const [agentic, setAgentic] = useState(true)
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [error, setError] = useState('')
  const [showTrace, setShowTrace] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped?.name.endsWith('.md')) {
      setFile(dropped)
      setResult(null)
      setError('')
    } else {
      setError('Only .md files are supported.')
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) {
      setFile(f)
      setResult(null)
      setError('')
    }
  }

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const data = agentic ? await uploadMdAgentic(file) : await uploadMd(file)
      setResult(data)
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (e: any) {
      setError(e.response?.data?.detail ?? 'Upload failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    setSyncMsg('')
    try {
      const data = await syncQuestions()
      setSyncMsg(data.status ?? 'Sync complete.')
    } catch (e: any) {
      setSyncMsg(e.response?.data?.detail ?? 'Sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-200">Upload Questions</h2>

        {/* Sync from file button */}
        <div className="flex items-center gap-3">
          {syncMsg && <span className="text-xs text-slate-400">{syncMsg}</span>}
          <button
            onClick={handleSync}
            disabled={syncing}
            className="text-xs px-3 py-1.5 bg-slate-800 border border-slate-700 hover:border-slate-500 text-slate-300 rounded-lg transition-colors disabled:opacity-50"
          >
            {syncing ? 'Syncing…' : 'Sync from DSA_Must_Solve_Problems.md'}
          </button>
        </div>
      </div>

      {/* Mode toggle */}
      <div className="flex items-center gap-1 bg-slate-800 rounded-xl p-1 w-fit">
        <button
          onClick={() => setAgentic(false)}
          className={`px-4 py-1.5 text-sm rounded-lg font-medium transition-colors ${
            !agentic ? 'bg-slate-700 text-slate-100' : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          Standard Import
        </button>
        <button
          onClick={() => setAgentic(true)}
          className={`px-4 py-1.5 text-sm rounded-lg font-medium transition-colors ${
            agentic ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          ✦ Agentic Import
        </button>
      </div>

      {!agentic ? (
        <p className="text-xs text-slate-500">
          Parses question titles from markdown headings and inserts them with default metadata.
        </p>
      ) : (
        <p className="text-xs text-slate-500">
          An AI agent reads the file, deduplicates, classifies each question (pattern, difficulty, category),
          generates a hint, and returns a rich import report.
        </p>
      )}

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl px-6 py-10 text-center cursor-pointer transition-colors ${
          dragging
            ? 'border-blue-500 bg-blue-900/10'
            : file
            ? 'border-green-600 bg-green-900/10'
            : 'border-slate-700 hover:border-slate-500 bg-slate-800/30'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".md"
          onChange={handleFileChange}
          className="hidden"
        />
        {file ? (
          <div>
            <p className="text-green-400 font-medium">{file.name}</p>
            <p className="text-xs text-slate-500 mt-1">{(file.size / 1024).toFixed(1)} KB · ready to upload</p>
          </div>
        ) : (
          <div>
            <p className="text-3xl mb-3">📄</p>
            <p className="text-slate-300 text-sm">Drag & drop a <span className="font-mono">.md</span> file here</p>
            <p className="text-slate-600 text-xs mt-1">or click to browse</p>
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700/50 rounded-xl px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {file && (
        <button
          onClick={handleUpload}
          disabled={loading}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded-xl transition-colors text-sm flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-white" />
              {agentic ? 'Agent is importing questions…' : 'Importing…'}
            </>
          ) : (
            `Upload with ${agentic ? 'AI Agent' : 'Standard Parser'}`
          )}
        </button>
      )}

      {loading && agentic && (
        <p className="text-xs text-slate-500 text-center">
          This may take 30–90 seconds depending on the number of questions.
          Watch the Agent Logs tab for live progress.
        </p>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="bg-slate-800 border border-slate-700 rounded-2xl p-5 space-y-3">
            <div className="flex items-center gap-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-green-400">{result.total_added}</p>
                <p className="text-xs text-slate-500">Added</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-slate-400">{result.total_skipped}</p>
                <p className="text-xs text-slate-500">Skipped (duplicates)</p>
              </div>
              {result.total_tool_calls != null && (
                <div className="text-center">
                  <p className="text-2xl font-bold text-blue-400">{result.total_tool_calls}</p>
                  <p className="text-xs text-slate-500">Agent tool calls</p>
                </div>
              )}
            </div>
            {result.summary && (
              <p className="text-sm text-slate-300 border-t border-slate-700 pt-3">{result.summary}</p>
            )}
          </div>

          {/* Added list */}
          {result.added.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-slate-300 mb-2">
                Added questions ({result.added.length})
              </h3>
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {result.added.map((q, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 px-3 py-2 bg-green-900/20 border border-green-800/30 rounded-lg"
                  >
                    <span className="text-green-500 flex-shrink-0 mt-0.5">✓</span>
                    <div className="min-w-0">
                      <p className="text-sm text-slate-200 font-medium">{q.title}</p>
                      <p className="text-xs text-slate-500">
                        {q.pattern} · {q.difficulty}
                        {q.hint && <span className="ml-2 italic text-slate-600">— {q.hint}</span>}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Skipped list */}
          {result.skipped_duplicates.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-slate-400 mb-2">
                Skipped ({result.skipped_duplicates.length} duplicates)
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {result.skipped_duplicates.map((t, i) => (
                  <span
                    key={i}
                    className="text-xs bg-slate-800 border border-slate-700 text-slate-500 px-2 py-0.5 rounded-md"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Agent trace (collapsible) */}
          {result.trace && result.trace.length > 0 && (
            <div>
              <button
                onClick={() => setShowTrace((v) => !v)}
                className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 transition-colors"
              >
                <span>{showTrace ? '▾' : '▸'}</span>
                Agent trace ({result.trace.length} steps)
              </button>

              {showTrace && (
                <div className="mt-2 space-y-1 max-h-80 overflow-y-auto border border-slate-800 rounded-xl">
                  {result.trace.map((t) => (
                    <div
                      key={t.step}
                      className={`flex gap-3 px-3 py-2 border-b border-slate-800/50 text-xs ${
                        t.is_error ? 'bg-red-900/20' : ''
                      }`}
                    >
                      <span className="text-slate-600 w-6 flex-shrink-0">#{t.step}</span>
                      <span className="font-mono text-yellow-400 flex-shrink-0">{t.tool}</span>
                      <span className="text-slate-400 flex-1">{t.result_summary}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
