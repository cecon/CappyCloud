import type { ProjectSuggestionCard } from '../../api'

export type QuickAction = {
  key: string
  icon: string
  iconColor: string
  title: string
  desc: string
  disabled?: boolean
}

export function buildProjectQuickActions({
  repoName,
  suggestions,
  hasSelection,
}: {
  repoName: string
  suggestions: ProjectSuggestionCard[]
  hasSelection: boolean
}): QuickAction[] {
  if (suggestions.length > 0) {
    return suggestions.slice(0, 4).map((suggestion) => ({
      key: suggestion.id,
      icon: iconForSuggestion(suggestion.category),
      iconColor: colorForSuggestion(suggestion.category),
      title: suggestion.title,
      desc: suggestion.prompt,
    }))
  }
  const subject = hasSelection ? repoName : 'o projeto escolhido'
  return [
    {
      key: 'fallback-explore',
      icon: 'travel_explore',
      iconColor: 'var(--cc-primary)',
      title: 'Explore e entenda',
      desc: `Analise ${subject} e explique arquitetura, fluxos principais e pontos de atenção.`,
    },
    {
      key: 'fallback-build',
      icon: 'construction',
      iconColor: 'var(--cc-secondary)',
      title: 'Crie algo útil',
      desc: `Sugira uma melhoria pequena para ${subject} e implemente com testes focados.`,
    },
    {
      key: 'fallback-review',
      icon: 'published_with_changes',
      iconColor: 'var(--cc-success)',
      title: 'Revise o código',
      desc: `Revise ${subject} procurando bugs, riscos e mudanças importantes.`,
    },
    {
      key: 'fallback-fix',
      icon: 'bug_report',
      iconColor: 'var(--cc-error)',
      title: 'Corrija problemas',
      desc: `Investigue os problemas mais prováveis em ${subject} e proponha validações.`,
    },
  ]
}

function iconForSuggestion(category: string): string {
  if (category === 'build') return 'construction'
  if (category === 'review') return 'published_with_changes'
  if (category === 'fix') return 'bug_report'
  if (category === 'support') return 'support_agent'
  return 'travel_explore'
}

function colorForSuggestion(category: string): string {
  if (category === 'build') return 'var(--cc-secondary)'
  if (category === 'review') return 'var(--cc-success)'
  if (category === 'fix') return 'var(--cc-error)'
  if (category === 'support') return 'var(--muted-foreground)'
  return 'var(--cc-primary)'
}
