import React, { useState } from 'react'
import { Alert, Button, Container, Paper, PasswordInput, Stack, Text, Title } from '@/components/ui/legacy'
import { useNavigate } from 'react-router-dom'
import { changePasswordRequest, errorToUserMessage, getToken } from '../api'

export function ChangePasswordPage() {
  const navigate = useNavigate()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault()
    const token = getToken()
    if (!token) {
      navigate('/login', { replace: true })
      return
    }
    if (!currentPassword) {
      setFormError('Informe a senha atual.')
      return
    }
    if (newPassword.length < 8) {
      setFormError('A nova senha deve ter pelo menos 8 caracteres.')
      return
    }
    if (newPassword !== confirmPassword) {
      setFormError('A confirmação não confere com a nova senha.')
      return
    }

    setLoading(true)
    setFormError(null)
    try {
      await changePasswordRequest(token, currentPassword, newPassword)
      navigate('/', { replace: true })
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Container size={460} py={80}>
      <Title order={2} ta="center" mb="md">
        Alterar senha
      </Title>
      <Text c="dimmed" size="sm" ta="center" mb="lg">
        Defina uma senha própria para continuar usando o CappyCloud.
      </Text>
      <Paper withBorder shadow="md" p={30} radius="md">
        <form onSubmit={handleSubmit}>
          <Stack gap="md">
            {formError && (
              <Alert color="red" title="Não foi possível alterar">
                {formError}
              </Alert>
            )}
            <PasswordInput
              label="Senha atual"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.currentTarget.value)}
              autoComplete="current-password"
              required
            />
            <PasswordInput
              label="Nova senha"
              description="Mínimo 8 caracteres."
              value={newPassword}
              onChange={(e) => setNewPassword(e.currentTarget.value)}
              autoComplete="new-password"
              required
            />
            <PasswordInput
              label="Confirmar nova senha"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.currentTarget.value)}
              autoComplete="new-password"
              required
            />
            <Button type="submit" loading={loading} fullWidth>
              Salvar senha
            </Button>
          </Stack>
        </form>
      </Paper>
    </Container>
  )
}
