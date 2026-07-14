import React, { useState } from 'react'
import { LockKeyhole, LogIn, Mail } from 'lucide-react'
import { errorToUserMessage, loginRequest, setToken } from '../api'
import { BrandMark } from '../components/layout/BrandMark'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { isPlausibleEmail } from '../validation'

type Props = {
  onLoggedIn: () => void
}

export function LoginPage({ onLoggedIn }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [emailError, setEmailError] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  function validateEmail(): boolean {
    const normalizedEmail = email.trim().toLowerCase()
    if (!normalizedEmail) {
      setEmailError('Informe seu email.')
      return false
    }
    if (!isPlausibleEmail(normalizedEmail)) {
      setEmailError('Email inválido. Use o formato nome@dominio.com.')
      return false
    }
    setEmailError(null)
    return true
  }

  function validatePassword(): boolean {
    if (!password) {
      setPasswordError('Informe a senha.')
      return false
    }
    setPasswordError(null)
    return true
  }

  async function handleLogin(e?: React.FormEvent) {
    e?.preventDefault()
    const emailOk = validateEmail()
    const passwordOk = validatePassword()
    if (!emailOk || !passwordOk) return

    setLoading(true)
    setApiError(null)
    try {
      const token = await loginRequest(email.trim().toLowerCase(), password)
      setToken(token)
      onLoggedIn()
    } catch (e) {
      setApiError(errorToUserMessage(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-dvh overflow-y-auto bg-background text-foreground">
      <div className="mx-auto flex min-h-dvh w-full max-w-6xl box-border items-center justify-center px-5 py-2 md:px-8 lg:px-10">
        <section className="w-full max-w-[430px]">
          <form
            onSubmit={handleLogin}
            className="rounded-lg border border-border bg-card p-5 shadow-[0_18px_60px_rgba(0,0,0,0.16)] md:p-6"
          >
            <div className="mb-6">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-muted">
                  <BrandMark className="h-10 w-10" />
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
                    CappyCloud
                  </p>
                  <h2 className="text-xl font-bold tracking-normal">Acesse sua conta</h2>
                </div>
              </div>
              <p className="text-sm leading-6 text-muted-foreground">
                Use as credenciais criadas pelo administrador.
              </p>
            </div>

            {apiError && (
              <div
                className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
                role="alert"
              >
                {apiError}
              </div>
            )}

            <div className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="login-email" className="text-sm font-medium">
                  Email
                </label>
                <div className="relative">
                  <Mail
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <Input
                    id="login-email"
                    className="h-11 pl-9"
                    placeholder="nome@dominio.com"
                    type="email"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.currentTarget.value)
                      if (emailError) setEmailError(null)
                    }}
                    onBlur={validateEmail}
                    autoComplete="email"
                    aria-invalid={Boolean(emailError)}
                    aria-describedby={emailError ? 'login-email-error' : undefined}
                  />
                </div>
                {emailError && (
                  <p id="login-email-error" className="text-xs text-destructive">
                    {emailError}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <label htmlFor="login-password" className="text-sm font-medium">
                  Senha
                </label>
                <div className="relative">
                  <LockKeyhole
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <Input
                    id="login-password"
                    className="h-11 pl-9"
                    type="password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.currentTarget.value)
                      if (passwordError) setPasswordError(null)
                    }}
                    onBlur={validatePassword}
                    autoComplete="current-password"
                    aria-invalid={Boolean(passwordError)}
                    aria-describedby={passwordError ? 'login-password-error' : undefined}
                  />
                </div>
                {passwordError && (
                  <p id="login-password-error" className="text-xs text-destructive">
                    {passwordError}
                  </p>
                )}
              </div>

              <Button type="submit" className="h-11 w-full font-semibold" disabled={loading}>
                {loading ? (
                  'Entrando...'
                ) : (
                  <>
                    Entrar
                    <LogIn className="h-4 w-4" aria-hidden="true" />
                  </>
                )}
              </Button>
            </div>

            <p className="mt-5 text-center text-xs text-muted-foreground">
              Contas são criadas por um administrador.
            </p>
          </form>
        </section>
      </div>
    </main>
  )
}
