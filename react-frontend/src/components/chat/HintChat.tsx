import { useState, useRef, useEffect } from 'react'
import { hintChat } from '../../api/client'
import type { ChatMessage, Question } from '../../types'

interface Props {
  question: Question
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-blue-700 flex items-center justify-center mr-2 mt-0.5 flex-shrink-0">
          <span className="text-xs font-bold text-white">AI</span>
        </div>
      )}
      <div
        className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed chat-assistant ${
          isUser
            ? 'bg-blue-600 text-white rounded-br-sm'
            : 'bg-slate-800 border border-slate-700 text-slate-200 rounded-bl-sm'
        }`}
      >
        {msg.content.split('\n').map((line, i) => (
          <span key={i}>
            {line}
            {i < msg.content.split('\n').length - 1 && <br />}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function HintChat({ question }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMessages([])
    setInput('')
  }, [question.id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return

    const userMsg: ChatMessage = { role: 'user', content: text }
    const updated = [...messages, userMsg]
    setMessages(updated)
    setInput('')
    setLoading(true)

    try {
      const res = await hintChat(question.id, {
        message: text,
        context: {
          title: question.title,
          pattern: question.pattern,
          difficulty: question.difficulty,
          notes: question.notes ?? '',
          gap_analysis: question.my_gap_analysis ?? '',
          accuracy: question.accuracy,
        },
        history: messages.map((m) => ({ role: m.role, content: m.content })),
        generate_variations: false,
      })
      setMessages([...updated, { role: 'assistant', content: res.reply }])
    } catch (e: any) {
      setMessages([
        ...updated,
        { role: 'assistant', content: `Error: ${e.response?.data?.detail ?? 'AI unavailable'}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const generateVariations = async () => {
    setLoading(true)
    const varMsg: ChatMessage = { role: 'user', content: 'Generate 3 problem variations' }
    const updated = [...messages, varMsg]
    setMessages(updated)
    try {
      const res = await hintChat(question.id, {
        message: varMsg.content,
        context: {},
        history: messages.map((m) => ({ role: m.role, content: m.content })),
        generate_variations: true,
      })
      setMessages([...updated, { role: 'assistant', content: res.reply }])
    } catch (e: any) {
      setMessages([
        ...updated,
        { role: 'assistant', content: `Error: ${e.response?.data?.detail ?? 'AI unavailable'}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Question context strip */}
      <div className="flex-shrink-0 px-4 py-2 bg-slate-800/50 border-b border-slate-700 text-xs text-slate-400">
        <span className="font-medium text-slate-300">{question.title}</span>
        <span className="mx-1.5">·</span>
        <span>{question.pattern}</span>
        <span className="mx-1.5">·</span>
        <span>{question.difficulty}</span>
        {question.hint && (
          <p className="mt-1 text-slate-500 italic truncate">💡 {question.hint}</p>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="text-center text-slate-600 text-sm mt-6">
            <p className="mb-4">Ask for a hint, explain your approach, or explore variations.</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {[
                'What approach should I use?',
                'What data structure fits here?',
                'Walk me through the algorithm',
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-full text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} msg={m} />
        ))}
        {loading && (
          <div className="flex justify-start mb-3">
            <div className="w-7 h-7 rounded-full bg-blue-700 flex items-center justify-center mr-2 flex-shrink-0">
              <span className="text-xs font-bold text-white">AI</span>
            </div>
            <div className="bg-slate-800 border border-slate-700 rounded-2xl rounded-bl-sm px-4 py-3">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Action shortcuts */}
      {messages.length === 0 && (
        <div className="px-4 pb-2">
          <button
            onClick={generateVariations}
            disabled={loading}
            className="text-xs text-purple-400 hover:text-purple-300 transition-colors disabled:opacity-40"
          >
            ✦ Generate 3 problem variations
          </button>
        </div>
      )}

      {/* Input */}
      <div className="flex-shrink-0 p-3 border-t border-slate-800 bg-slate-900">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask for a hint… (Enter to send)"
            rows={2}
            className="flex-1 bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-xl px-3 py-2 resize-none focus:outline-none focus:border-blue-500 placeholder-slate-600 transition-colors"
          />
          <button
            onClick={send}
            disabled={!input.trim() || loading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl transition-colors flex-shrink-0"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
