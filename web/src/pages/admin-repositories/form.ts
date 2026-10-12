import type { Repository, RepositoryCreate } from '../../api'

export type FormState = {
  slug: string
  name: string
  clone_url: string
  default_branch: string
  confluence_url: string
  confluence_space: string
  confluence_labels: string
  pat_token: string
  sandbox_id: string | null
}

export const EMPTY_FORM: FormState = {
  slug: '',
  name: '',
  clone_url: '',
  default_branch: 'main',
  confluence_url: '',
  confluence_space: '',
  confluence_labels: '',
  pat_token: '',
  sandbox_id: null,
}

function parseLabels(value: string): string[] {
  const seen = new Set<string>()
  return value
    .split(',')
    .map((label) => label.trim().toLowerCase())
    .filter((label) => {
      if (!label || seen.has(label)) return false
      seen.add(label)
      return true
    })
}

function labelsToText(labels: string[] | null | undefined): string {
  return labels?.join(', ') ?? ''
}

export function formFromRepository(repo: Repository): FormState {
  return {
    slug: repo.slug,
    name: repo.name,
    clone_url: repo.clone_url,
    default_branch: repo.default_branch,
    confluence_url: repo.confluence_url,
    confluence_space: repo.confluence_space,
    confluence_labels: labelsToText(repo.confluence_labels),
    pat_token: '',
    sandbox_id: repo.sandbox_id,
  }
}

export function statusColor(s: string): string {
  if (s === 'cloned') return 'green'
  if (s === 'cloning') return 'yellow'
  if (s === 'error') return 'red'
  return 'gray'
}

export function buildPayload(form: FormState, existing?: Repository): RepositoryCreate {
  return {
    slug: form.slug.trim(),
    name: form.name.trim(),
    clone_url: form.clone_url.trim(),
    default_branch: form.default_branch.trim() || 'main',
    confluence_url: form.confluence_url.trim(),
    confluence_space: form.confluence_space.trim(),
    confluence_labels: parseLabels(form.confluence_labels),
    pat_token: form.pat_token.trim() || null,
    provider_id: existing?.provider_id ?? null,
    sandbox_id: form.sandbox_id || null,
    signoz_service_name: existing?.signoz_service_name ?? null,
  }
}
