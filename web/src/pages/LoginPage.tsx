import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Anchor,
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

/**
 * Página de login; registo em `/register`.
 */
export function LoginPage({ onLoggedIn }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleLogin() {
    const em = email.trim().toLowerCase()
    if (!em) {
      setError('Indica o teu email.')
      return
    }
    if (!isPlausibleEmail(em)) {
      setError('Email inválido. Usa o formato nome@dominio.com (ex.: nome@gmail.com).')
      return
    }
    if (!password) {
      setError('Indica a password.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const token = await loginRequest(em, password)
      setToken(token)
      onLoggedIn()
    } catch (e) {
      setError(errorToUserMessage(e))
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
        Agente de código com sandbox isolado — stack própria (FastAPI + React).
      </Text>
      <Paper withBorder shadow="md" p={30} radius="md">
        <Stack gap="md">
          {error && (
            <Text c="red" size="sm">
              {error}
            </Text>
          )}
          <TextInput
            label="Email"
            placeholder="nome@gmail.com"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.currentTarget.value)}
            autoComplete="email"
          />
          <PasswordInput
            label="Password"
            value={password}
            onChange={(e) => setPassword(e.currentTarget.value)}
            autoComplete="current-password"
          />
          <Button loading={loading} onClick={handleLogin} fullWidth>
            Entrar
          </Button>
          <Text size="sm" ta="center">
            Novo aqui?{' '}
            <Anchor component={Link} to="/register" underline="hover">
              Criar conta
            </Anchor>
          </Text>
        </Stack>
      </Paper>
    </Container>
  )
}
