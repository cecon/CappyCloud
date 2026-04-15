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
import { errorToUserMessage, loginRequest, registerRequest, setToken } from '../api'
import { isPlausibleEmail } from '../validation'

type Props = {
  onLoggedIn: () => void
}

/**
 * Página dedicada ao registo de nova conta.
 */
export function RegisterPage({ onLoggedIn }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleRegister() {
    const em = email.trim().toLowerCase()
    if (!em) {
      setError('Indica o teu email.')
      return
    }
    if (!isPlausibleEmail(em)) {
      setError('Email inválido. Usa o formato nome@dominio.com (ex.: nome@gmail.com).')
      return
    }
    if (password.length < 8) {
      setError('A password deve ter pelo menos 8 caracteres.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await registerRequest(em, password)
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
        Criar conta
      </Title>
      <Text c="dimmed" size="sm" ta="center" mb="lg">
        CappyCloud — regista-te para começar.
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
            description="Mínimo 8 caracteres (regra da API)."
            value={password}
            onChange={(e) => setPassword(e.currentTarget.value)}
            autoComplete="new-password"
            minLength={8}
          />
          <Button loading={loading} onClick={handleRegister} fullWidth>
            Registar
          </Button>
          <Text size="sm" ta="center">
            Já tens conta?{' '}
            <Anchor component={Link} to="/login" underline="hover">
              Entrar
            </Anchor>
          </Text>
        </Stack>
      </Paper>
    </Container>
  )
}
