import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { loginUrl } from '../api/auth'

export default function Login() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-surface text-ink-muted">
        Loading…
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="relative flex h-screen items-center justify-center mesh-bg text-ink overflow-hidden animate-fade-in">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 -left-32 h-96 w-96 rounded-full bg-brand/20 blur-3xl animate-float"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-cyan-400/20 blur-3xl animate-float [animation-delay:1.5s]"
      />

      <div className="relative w-full max-w-sm rounded-2xl glass-panel p-8 animate-slide-up-fade shadow-[0_0_40px_rgba(99,102,241,0.15)]">
        <div className="mb-5 flex items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-cyan-400 text-white font-bold shadow-[0_0_15px_rgba(99,102,241,0.5)]">
            <span className="relative z-10">N</span>
            <div className="absolute inset-0 rounded-xl bg-white/20 blur-sm mix-blend-overlay" />
          </div>
          <span className="text-lg font-semibold tracking-tight text-ink">Nexparse</span>
        </div>

        <h1 className="mb-2 text-3xl font-semibold tracking-tight">
          <span className="text-gradient">Welcome back</span>
        </h1>
        <p className="mb-7 text-sm text-ink-muted">
          Sign in to access your documents.
        </p>

        <div className="flex flex-col gap-3">
          <a
            href={loginUrl('google')}
            className="group flex items-center justify-center gap-3 rounded-xl border border-surface-border bg-surface-subtle px-4 py-2.5 text-sm font-medium text-ink transition-all duration-200 hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-card-hover hover:bg-surface-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:ring-offset-2 focus:ring-offset-surface"
          >
            <GoogleIcon className="h-5 w-5" />
            <span>Continue with Google</span>
          </a>
          <a
            href={loginUrl('github')}
            className="group flex items-center justify-center gap-3 rounded-xl border border-surface-border bg-surface-subtle px-4 py-2.5 text-sm font-medium text-ink transition-all duration-200 hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-card-hover hover:bg-surface-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:ring-offset-2 focus:ring-offset-surface"
          >
            <GitHubIcon className="h-5 w-5 text-ink" />
            <span>Continue with GitHub</span>
          </a>
        </div>

        <p className="mt-7 text-center text-xs text-ink-faint">
          Secure sign-in via OAuth. We never see your password.
        </p>
      </div>
    </div>
  )
}

function GoogleIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  )
}

function GitHubIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56 0-.28-.01-1.02-.02-2-3.2.7-3.87-1.54-3.87-1.54-.52-1.33-1.27-1.68-1.27-1.68-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.69 1.25 3.34.96.1-.74.4-1.25.72-1.54-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.18-3.1-.12-.29-.51-1.46.11-3.04 0 0 .97-.31 3.18 1.18.92-.26 1.92-.39 2.91-.39.99 0 1.99.13 2.91.39 2.21-1.49 3.18-1.18 3.18-1.18.62 1.58.23 2.75.11 3.04.74.81 1.18 1.84 1.18 3.1 0 4.43-2.7 5.41-5.27 5.69.41.35.78 1.05.78 2.12 0 1.53-.01 2.77-.01 3.14 0 .31.21.67.8.56C20.21 21.39 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z" />
    </svg>
  )
}
