import React, { useState } from 'react'
import {
  Button,
  Container,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { errorToUserMessage, loginRequest, setToken } from '../api'
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
    const em = email.trim().toLowerCase()
    if (!em) { setEmailError('Indica o teu email.'); return false }
    if (!isPlausibleEmail(em)) { setEmailError('Email inválido. Usa o formato nome@dominio.com.'); return false }
    setEmailError(null)
    return true
  }

  function validatePassword(): boolean {
    if (!password) { setPasswordError('Indica a senha.'); return false }
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
    <Container size={420} py={80}>
      <Title order={2} ta="center" mb="md">
        CappyCloud
      </Title>
      <Text c="dimmed" size="sm" ta="center" mb="lg">
        Agente de código com sandbox isolado na nuvem.
      </Text>
      <Paper withBorder shadow="md" p={30} radius="md">
        <form onSubmit={handleLogin}>
          <Stack gap="md">
            {apiError && (
              <Text c="red" size="sm" role="alert">
                {apiError}
              </Text>
            )}
            <TextInput
              label="Email"
              placeholder="nome@exemplo.com"
              type="email"
              value={email}
              onChange={(e) => { setEmail(e.currentTarget.value); if (emailError) setEmailError(null) }}
              onBlur={validateEmail}
              error={emailError}
              autoComplete="email"
            />
            <PasswordInput
              label="Senha"
              value={password}
              onChange={(e) => { setPassword(e.currentTarget.value); if (passwordError) setPasswordError(null) }}
              onBlur={validatePassword}
              error={passwordError}
              autoComplete="current-password"
            />
            <Button type="submit" loading={loading} fullWidth>
              Entrar
            </Button>
            <Text size="xs" c="dimmed" ta="center">
              Contas são criadas por um administrador.
            </Text>
          </Stack>
        </form>
      </Paper>
    </Container>
  )
}
