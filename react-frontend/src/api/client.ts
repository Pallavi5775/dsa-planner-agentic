import axios from 'axios'
import { useAuthStore } from '../store/auth'

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${BASE}/api`,
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().clearAuth()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Auth URLs (direct backend navigation for OAuth) ────────────────────────
export const authUrls = {
  microsoft: `${BASE}/api/auth/microsoft`,
  google: `${BASE}/api/auth/google`,
  github: `${BASE}/api/auth/github`,
  microsoftConnect: `${BASE}/api/auth/microsoft/connect`,
}

// ── Questions ──────────────────────────────────────────────────────────────
export const getQuestions = () => api.get('/questions').then((r) => r.data)

export const createQuestion = (data: {
  title: string
  pattern: string
  category: string
  difficulty: string
  hint?: string
}) => api.post('/questions', data).then((r) => r.data)

export const updateQuestion = (
  id: number,
  data: { title: string; pattern: string; category: string; difficulty: string; hint?: string }
) => api.put(`/questions/${id}`, data).then((r) => r.data)

export const addLog = (
  id: number,
  log: { code: string; logic: string; time_taken: number; correct: boolean; hint_used: boolean }
) => api.post(`/questions/${id}/log`, log).then((r) => r.data)

export const updateNotes = (id: number, notes: string, my_gap_analysis: string) =>
  api.patch(`/questions/${id}/notes`, { notes, my_gap_analysis }).then((r) => r.data)

export const updateHint = (id: number, hint: string) =>
  api
    .patch(`/questions/${id}/hint`, JSON.stringify(hint), {
      headers: { 'Content-Type': 'application/json' },
    })
    .then((r) => r.data)

export const generateDescription = (id: number) =>
  api.post(`/questions/${id}/description`).then((r) => r.data)

export const hintChat = (
  id: number,
  body: {
    message: string
    context?: Record<string, unknown>
    history?: { role: string; content: string }[]
    generate_variations?: boolean
  }
) => api.post(`/questions/${id}/chat`, body).then((r) => r.data)

export const validateQuestion = (id: number) =>
  api.post(`/questions/${id}/validate`).then((r) => r.data)

export const variationReview = (
  id: number,
  data: { variation_title: string; variation_description: string; code: string; notes: string }
) => api.post(`/questions/${id}/variation-review`, data).then((r) => r.data)

export const updateStatus = (
  id: number,
  category: string,
  coverage_status: string,
  revision_status: string
) =>
  api
    .put(`/questions/${id}/status`, { category, coverage_status, revision_status })
    .then((r) => r.data)

export const syncQuestions = () => api.post('/sync_questions').then((r) => r.data)

// ── Admin ──────────────────────────────────────────────────────────────────
export const getAgentLogs = (limit = 200) =>
  api.get('/admin/agent-logs', { params: { limit } }).then((r) => r.data)

export const clearAgentLogs = () => api.delete('/admin/agent-logs').then((r) => r.data)

export const uploadMd = (file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/upload_md', fd).then((r) => r.data)
}

export const uploadMdAgentic = (file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/upload_md/agentic', fd).then((r) => r.data)
}

export const getUsers = () => api.get('/users').then((r) => r.data)

export const createUser = (data: { email: string; username?: string; role: string }) =>
  api.post('/users', data).then((r) => r.data)

export const deleteUser = (id: number) => api.delete(`/users/${id}`).then((r) => r.data)

// ── Activity ───────────────────────────────────────────────────────────────
export const getActivity = (tz = 'UTC') =>
  api.get('/activity', { params: { tz } }).then((r) => r.data)

// ── Pattern notes ──────────────────────────────────────────────────────────
export const getPatternNotes = () => api.get('/pattern-notes').then((r) => r.data)

export const updatePatternNote = (
  pattern: string,
  notes: string,
  memory_techniques: string
) => api.patch('/pattern-notes', { pattern, notes, memory_techniques }).then((r) => r.data)

export const patternChat = (pattern: string, message: string, generate_memo = false) =>
  api.post('/pattern-chat', { pattern, message, generate_memo }).then((r) => r.data)
