import { ActionIcon, Button, Group, PasswordInput, Stack, Text, TextInput } from '@/components/ui/legacy'
import type { FormState } from './form'

/** Lista editável de variáveis de ambiente do MCP (chave + valor oculto). */
export function McpEnvEditor({ form, setForm }: { form: FormState; setForm: (form: FormState) => void }) {
  return (
    <Stack gap={6}>
      <Text size="sm" fw={500}>
        Variáveis de ambiente
      </Text>
      {form.envEntries.map((row, idx) => (
        <Group key={idx} gap="xs">
          <TextInput
            placeholder="KEY"
            value={row.key}
            onChange={(e) =>
              setForm({
                ...form,
                envEntries: form.envEntries.map((r, i) =>
                  i === idx ? { ...r, key: e.currentTarget.value } : r,
                ),
              })
            }
            style={{ flex: 1 }}
          />
          <PasswordInput
            placeholder="valor"
            value={row.value}
            onChange={(e) =>
              setForm({
                ...form,
                envEntries: form.envEntries.map((r, i) =>
                  i === idx ? { ...r, value: e.currentTarget.value } : r,
                ),
              })
            }
            style={{ flex: 2 }}
          />
          <ActionIcon
            variant="subtle"
            color="red"
            onClick={() =>
              setForm({
                ...form,
                envEntries: form.envEntries.filter((_, i) => i !== idx),
              })
            }
            disabled={form.envEntries.length === 1}
          >
            ×
          </ActionIcon>
        </Group>
      ))}
      <Button
        size="xs"
        variant="default"
        onClick={() =>
          setForm({ ...form, envEntries: [...form.envEntries, { key: '', value: '' }] })
        }
      >
        + adicionar variável
      </Button>
    </Stack>
  )
}
