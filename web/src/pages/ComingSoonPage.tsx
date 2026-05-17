import { Badge, Container, Group, Paper, Stack, Text, Title } from '@mantine/core'

type Props = {
  /** Título principal da página stub. */
  title: string
  /** Frase curta sobre o que o cadastro vai fazer. */
  description: string
  /** PR onde a feature será entregue (ex.: "PR2"). Mostrado como badge. */
  plannedIn: string
  /** Link/identificador da ADR que documenta a decisão (ADR-004, ADR-005, ADR-006). */
  adr: string
}

/**
 * Placeholder usado nas rotas de Cadastros que ainda não foram implementadas.
 * Mantém o menu coerente sem entregar UI inacabada; o badge "em breve" no menu
 * + o aviso aqui dão sinalização clara.
 */
export function ComingSoonPage({ title, description, plannedIn, adr }: Props) {
  return (
    <Container size="md" py="xl">
      <Paper withBorder p="xl" radius="md" bg="dark.7">
        <Stack gap="md">
          <Group justify="space-between" align="flex-start">
            <Title order={2}>{title}</Title>
            <Badge color="yellow" variant="light">
              em breve · {plannedIn}
            </Badge>
          </Group>
          <Text c="dimmed">{description}</Text>
          <Text size="sm" c="dimmed">
            Decisão arquitetural: <strong>{adr}</strong>. O cadastro vai aparecer aqui assim que o{' '}
            {plannedIn} entrar.
          </Text>
        </Stack>
      </Paper>
    </Container>
  )
}
