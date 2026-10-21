import { Badge, Group, Switch, Table, Text } from '@/components/ui/legacy'
import { IconPencil, IconTrash } from '@tabler/icons-react'
import type { GlobalSkill, Sandbox } from '../../api'
import { ActionsCell, ActionsHeader, RowActionIcon } from '../../components/TableActions'

type GlobalSkillsTableProps = {
  skills: GlobalSkill[]
  sandboxById: Map<string, Sandbox>
  onToggle: (skill: GlobalSkill) => void
  onEdit: (skill: GlobalSkill) => void
  onDelete: (skill: GlobalSkill) => void
}

function AssignedSandboxes({
  skill,
  sandboxById,
}: {
  skill: GlobalSkill
  sandboxById: Map<string, Sandbox>
}) {
  if (skill.sandbox_ids.length === 0) {
    return (
      <Text size="sm" c="dimmed" fs="italic">
        Nenhuma
      </Text>
    )
  }
  return (
    <Group gap={6}>
      {skill.sandbox_ids.map((sandboxId) => (
        <Badge key={sandboxId} variant="light" color="blue">
          {sandboxById.get(sandboxId)?.name ?? sandboxId.slice(0, 8)}
        </Badge>
      ))}
    </Group>
  )
}

export function GlobalSkillsTable({
  skills,
  sandboxById,
  onToggle,
  onEdit,
  onDelete,
}: GlobalSkillsTableProps) {
  return (
    <Table verticalSpacing="sm" highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Nome</Table.Th>
          <Table.Th>Descrição</Table.Th>
          <Table.Th>Sandboxes</Table.Th>
          <Table.Th w={90}>Ativo</Table.Th>
          <ActionsHeader width={110} />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {skills.map((skill) => (
          <Table.Tr key={skill.id}>
            <Table.Td>
              <Text fw={600}>{skill.name}</Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm" lineClamp={2}>
                {skill.description || (
                  <Text span c="dimmed" fs="italic">
                    sem descrição
                  </Text>
                )}
              </Text>
            </Table.Td>
            <Table.Td>
              <AssignedSandboxes skill={skill} sandboxById={sandboxById} />
            </Table.Td>
            <Table.Td>
              <Switch
                checked={skill.enabled}
                onChange={() => onToggle(skill)}
                size="xs"
                aria-label={`Ativar ${skill.name}`}
              />
            </Table.Td>
            <ActionsCell>
              <RowActionIcon label="Editar" onClick={() => onEdit(skill)}>
                <IconPencil size={16} />
              </RowActionIcon>
              <RowActionIcon label="Apagar" color="red" onClick={() => onDelete(skill)}>
                <IconTrash size={16} />
              </RowActionIcon>
            </ActionsCell>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}
