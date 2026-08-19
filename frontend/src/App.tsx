import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { LogOut, Mail, Shield, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { signInWithEmail, signOut, signUpWithEmail } from '@/lib/auth'
import { supabase } from '@/lib/supabase'
import './App.css'

type Mode = 'signin' | 'signup'

function App() {
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [sessionEmail, setSessionEmail] = useState<string | null>(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSessionEmail(data.session?.user.email ?? null)
    })

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      setSessionEmail(session?.user.email ?? null)
    })

    return () => {
      subscription.subscription.unsubscribe()
    }
  }, [])

  const isSignedIn = useMemo(() => sessionEmail !== null, [sessionEmail])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setStatus(null)

    try {
      const action =
        mode === 'signup'
          ? signUpWithEmail(email, password)
          : signInWithEmail(email, password)
      const { error, data } = await action

      if (error) {
        throw error
      }

      if (mode === 'signup') {
        const confirmed = data.session ? 'You are signed up and signed in.' : 'Check your email to confirm your account.'
        setStatus(confirmed)
      } else {
        setStatus('Signed in.')
      }
      setPassword('')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSignOut() {
    setLoading(true)
    setStatus(null)
    try {
      const { error } = await signOut()
      if (error) {
        throw error
      }
      setSessionEmail(null)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Could not sign out.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <div className="auth-rail">
          <div className="auth-rail-top">
            <div className="auth-brand">
              <Sparkles className="size-4" />
              Document Copilot
            </div>
            <div>
              <h1 className="auth-title">
                Sign in with email. No SSO, no extra ceremony.
              </h1>
              <p className="auth-subtitle">
                Create an account, confirm your email if Supabase requires it, and
                you&apos;re ready to reach the backend with a real bearer token.
              </p>
            </div>
          </div>
          <div className="auth-notes">
            <div className="auth-note">
              <Shield className="size-4" />
              Supabase Auth handles the session
            </div>
            <div className="auth-note">
              <Mail className="size-4" />
              Email confirmations stay in the Supabase flow
            </div>
          </div>
        </div>

        <div className="auth-panel">
          <div className="auth-panel-inner">
            <div className="auth-header">
              <p className="auth-eyebrow">
                Authentication
              </p>
              <h2 className="auth-heading">
                {isSignedIn ? 'You are signed in' : mode === 'signup' ? 'Create your account' : 'Welcome back'}
              </h2>
            </div>

            {isSignedIn ? (
              <div className="auth-signed-in">
                <p className="auth-signed-in-text">
                  Signed in as <span>{sessionEmail}</span>
                </p>
                <Button type="button" onClick={handleSignOut} disabled={loading} className="auth-button">
                  <LogOut className="size-4" />
                  Sign out
                </Button>
              </div>
            ) : (
              <>
                <div className="auth-toggle">
                  <button
                    type="button"
                    onClick={() => setMode('signin')}
                    className={`auth-toggle-btn ${mode === 'signin' ? 'is-active' : ''}`}
                  >
                    Sign in
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode('signup')}
                    className={`auth-toggle-btn ${mode === 'signup' ? 'is-active' : ''}`}
                  >
                    Sign up
                  </button>
                </div>

                <form onSubmit={handleSubmit} className="auth-form">
                  <label className="auth-field">
                    <span>Email</span>
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="analyst@company.com"
                    />
                  </label>

                  <label className="auth-field">
                    <span>Password</span>
                    <input
                      type="password"
                      required
                      minLength={8}
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder="At least 8 characters"
                    />
                  </label>

                  <Button type="submit" disabled={loading} className="auth-button">
                    {mode === 'signup' ? 'Create account' : 'Sign in'}
                  </Button>
                </form>
              </>
            )}

            {status ? (
              <p className="auth-status">
                {status}
              </p>
            ) : null}
          </div>
        </div>
      </section>
    </main>
  )
}

export default App
