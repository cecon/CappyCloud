import { apiFetch, formatApiErrorPayload } from './http'

// ── Skills ───────────────────────────────────────────────────────────────────

export interface Skill {
  id: string
  repository_id: string | null
  slug: string
  title: string
  summary: string
  content: string
  tags: string[]
  source_url: string | null
  active: boolean
  has_embedding: boolean
  created_at: string
  updated_at: string
}

export interface SkillCreate {
  repository_id: string
  title: string
  slug?: string
  summary?: string
  content?: string | null
  tags?: string[]
  source_url?: string | null
}

export async function fetchSkills(token: string): Promise<Skill[]> {
  const res = await apiFetch('/api/skills', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export async function createSkill(token: string, data: SkillCreate): Promise<Skill> {
  const res = await apiFetch('/api/skills', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar skill')
  }
  return res.json()
}

export async function updateSkill(
  token: string,
  id: string,
  data: Partial<SkillCreate> & { active?: boolean },
): Promise<Skill> {
  const res = await apiFetch(`/api/skills/${id}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar skill')
  }
  return res.json()
}

export async function deleteSkill(token: string, id: string): Promise<void> {
  const res = await apiFetch(`/api/skills/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Falha ao remover skill')
}

export async function importSkillFromUrl(
  token: string,
  url: string,
  tags: string[] = [],
): Promise<Skill> {
  const body: Record<string, unknown> = { url, tags }
  const res = await apiFetch('/api/skills/import-url', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao importar URL')
  }
  return res.json()
}
