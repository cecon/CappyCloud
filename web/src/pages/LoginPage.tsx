import React, { useState } from 'react'
import { AlertCircle, LockKeyhole, Mail } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { errorToUserMessage, loginRequest, setToken } from '../api'
import { isPlausibleEmail } from '../validation'
import styles from './LoginPage.module.css'

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
    const em = email.trim().toLowerCase()
    if (!em) {
      setEmailError('Informe seu email.')
      return false
    }
    if (!isPlausibleEmail(em)) {
      setEmailError('Use o formato nome@dominio.com.')
      return false
    }
    setEmailError(null)
    return true
  }

  function validatePassword(): boolean {
    if (!password) {
      setPasswordError('Informe sua senha.')
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
    } catch (err) {
      setApiError(errorToUserMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.shell}>
        <Card className={styles.card}>
          <div className={styles.grid}>
            <div className={styles.brandPanel}>
              <div>
                <div className={styles.brandLockup}>
                  <span className={styles.logoFrame}>
                    <img src="/capybara.png" alt="" className={styles.logo} />
                  </span>
                  <div>
                    <p className={styles.eyebrow}>
                      CappyCloud
                    </p>
                    <h1 className={styles.brandTitle}>
                      Command Center
                    </h1>
                  </div>
                </div>

                <h2 className={styles.headline}>
                  Entre no seu workspace isolado.
                </h2>
                <p className={styles.copy}>
                  Converse com o agente, consulte repositorios, acompanhe execucoes e mantenha o
                  contexto em uma unica superficie.
                </p>
              </div>

              <div className={styles.stats}>
                <div className={styles.statCard}>
                  <p className={styles.statValue}>1</p>
                  <p className={styles.statLabel}>
                    workspace
                  </p>
                </div>
                <div className={styles.statCard}>
                  <p className={styles.statValue}>AI</p>
                  <p className={styles.statLabel}>
                    sandbox
                  </p>
                </div>
              </div>
            </div>

            <div className={styles.formPanel}>
              <form onSubmit={handleLogin} className={styles.form}>
                <div>
                  <p className={styles.eyebrow}>
                    Acesso
                  </p>
                  <h3 className={styles.formTitle}>Entrar no CappyCloud</h3>
                </div>

                {apiError && (
                  <div
                    className={styles.errorBox}
                    role="alert"
                  >
                    <AlertCircle className={styles.errorIcon} aria-hidden />
                    <span>{apiError}</span>
                  </div>
                )}

                <label className={styles.field}>
                  <span className={styles.label}>Email</span>
                  <span className={styles.inputWrap}>
                    <Mail className={styles.inputIcon} />
                    <Input
                      className={styles.input}
                      placeholder="nome@exemplo.com"
                      type="email"
                      value={email}
                      onChange={(e) => {
                        setEmail(e.currentTarget.value)
                        if (emailError) setEmailError(null)
                      }}
                      onBlur={validateEmail}
                      autoComplete="email"
                    />
                  </span>
                  {emailError && <span className={styles.fieldError}>{emailError}</span>}
                </label>

                <label className={styles.field}>
                  <span className={styles.label}>Senha</span>
                  <span className={styles.inputWrap}>
                    <LockKeyhole className={styles.inputIcon} />
                    <Input
                      className={styles.input}
                      type="password"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.currentTarget.value)
                        if (passwordError) setPasswordError(null)
                      }}
                      onBlur={validatePassword}
                      autoComplete="current-password"
                    />
                  </span>
                  {passwordError && <span className={styles.fieldError}>{passwordError}</span>}
                </label>

                <Button type="submit" className={styles.submit} disabled={loading}>
                  {loading ? 'Entrando...' : 'Entrar'}
                </Button>

                <p className={styles.footerText}>
                  Contas sao criadas por um administrador.
                </p>
              </form>
            </div>
          </div>
        </Card>
      </section>
    </main>
  )
}
