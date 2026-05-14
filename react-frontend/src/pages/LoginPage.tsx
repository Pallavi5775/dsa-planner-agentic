import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { authUrls } from '../api/client'

function MicrosoftIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="1" width="9" height="9" fill="#f25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
      <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
      <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
    </svg>
  )
}


export default function LoginPage() {
  const { token } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (token) navigate('/', { replace: true })
  }, [token, navigate])

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo / Brand */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-600 mb-4">
            <span className="text-2xl font-bold text-white">D</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-100">DSA Planner</h1>
          <p className="text-slate-400 mt-1 text-sm">Your intelligent DSA revision companion</p>
        </div>

        {/* Login card */}
        <div className="bg-slate-900 border border-slate-700 rounded-2xl p-8 shadow-2xl">
          <h2 className="text-lg font-semibold text-slate-200 mb-6 text-center">Sign in to continue</h2>

          <a
            href={authUrls.microsoft}
            className="flex items-center gap-3 w-full px-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition-colors duration-150 justify-center"
          >
            <MicrosoftIcon />
            Sign in with Microsoft
          </a>

          <p className="text-xs text-slate-500 text-center mt-6">
            Microsoft login enables OneDrive storage, Teams notifications, and Calendar integration.
          </p>
        </div>
      </div>
    </div>
  )
}
