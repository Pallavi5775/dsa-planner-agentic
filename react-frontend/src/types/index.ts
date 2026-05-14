export interface User {
  id: number
  username: string
  role: 'admin' | 'user'
  oauth_provider?: string
  github_username?: string
  avatar_url?: string
}

export interface PracticeLog {
  id: number
  question_id: number
  date: string
  logic: string
  code: string
  time_taken: number
  correct: boolean
  hint_used: boolean
}

export interface Question {
  id: number
  title: string
  pattern: string
  category: string
  difficulty: 'Easy' | 'Medium' | 'Hard'
  hint?: string
  description?: string
  coverage_status: string
  revision_status: string
  ease_factor: number
  interval_days: number
  next_revision?: string
  accuracy?: number
  suggestions?: string
  notes?: string
  my_gap_analysis?: string
  total_time_spent: number
  logs: PracticeLog[]
}

export interface AgentLogEntry {
  time: string
  agent: string
  type: 'start' | 'tool_call' | 'tool_result' | 'end'
  icon: string
  step?: number
  label: string
  detail: string
  is_error?: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface QuestionFilters {
  search: string
  pattern: string
  difficulty: string
  coverage: string
}

export interface AdminUser {
  id: number
  username: string
  email: string
  role: string
  oauth_provider?: string
}
