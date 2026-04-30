---
name: design-system
description: Use esta habilidade para gerar ou evoluir o design system do CappyCloud — tokens, paletas, tipografia, espaçamentos e padrões de componentes. Use ao criar novos módulos visuais, padronizar componentes existentes ou definir identidade visual de uma nova feature.
---

# Design System Generator — CappyCloud

Motor de geração de sistemas de design para o CappyCloud. Analisa o contexto da feature e produz especificações completas de tokens, componentes e padrões visuais.

## 1. Arquitetura de Tokens

### Camada 1 — Primitivos (CSS Variables globais)
Definidos em `web/src/index.css` ou tema Mantine:

```css
/* Cores base */
--color-dark-900: #0d0d0f;
--color-dark-800: #141417;
--color-dark-700: #1a1a1f;
--color-dark-600: #222228;
--color-dark-500: #2a2a32;
--color-dark-400: #3a3a45;
--color-dark-300: #5a5a6a;
--color-dark-200: #7a7a8a;
--color-dark-100: #b0b0be;
--color-dark-050: #e8e8ed;

/* Accent */
--color-blue-500: #4f8ef7;
--color-blue-400: #7aaeff;
--color-blue-600: #2d6dd4;
--color-green-500: #3ecf8e;
--color-red-500: #f04e4e;
--color-yellow-500: #f5a623;
--color-purple-500: #9b74f7;

/* Espaçamento */
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;
--space-12: 48px;

/* Tipografia */
--font-size-xs: 11px;
--font-size-sm: 13px;
--font-size-md: 14px;
--font-size-lg: 16px;
--font-size-xl: 20px;
--font-size-2xl: 24px;
--font-size-3xl: 32px;

/* Bordas */
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-xl: 16px;
--radius-full: 9999px;

/* Sombras */
--shadow-sm: 0 1px 3px rgba(0,0,0,0.4);
--shadow-md: 0 4px 12px rgba(0,0,0,0.5);
--shadow-lg: 0 8px 24px rgba(0,0,0,0.6);
```

### Camada 2 — Semântica (Aliases)
```css
--surface-base:    var(--color-dark-900);
--surface-raised:  var(--color-dark-800);
--surface-overlay: var(--color-dark-700);
--surface-input:   var(--color-dark-700);
--border-default:  var(--color-dark-500);
--border-focus:    var(--color-blue-500);
--text-primary:    var(--color-dark-050);
--text-secondary:  var(--color-dark-200);
--text-muted:      var(--color-dark-300);
--text-disabled:   var(--color-dark-400);
--accent-primary:  var(--color-blue-500);
--status-success:  var(--color-green-500);
--status-error:    var(--color-red-500);
--status-warning:  var(--color-yellow-500);
```

### Camada 3 — Componentes
```css
--button-primary-bg:      var(--accent-primary);
--button-primary-hover:   var(--color-blue-400);
--card-bg:                var(--surface-raised);
--card-border:            var(--border-default);
--input-bg:               var(--surface-input);
--input-border:           var(--border-default);
--input-border-focus:     var(--border-focus);
--sidebar-bg:             var(--surface-base);
--topbar-bg:              var(--surface-raised);
```

## 2. Catálogo de Componentes

### Componentes Base
| Componente | Mantine Base | Customização |
|-----------|-------------|-------------|
| `Button` primário | `<Button>` | `variant="filled"`, cor `blue` |
| `Button` secundário | `<Button>` | `variant="subtle"`, cor `gray` |
| `Button` destrutivo | `<Button>` | `variant="filled"`, cor `red` |
| `Input` | `<TextInput>` | bg `dark-7`, border `dark-4` |
| `Select` | `<Select>` | dropdown bg `dark-7` |
| `Card` | `<Paper>` | `withBorder`, `radius="md"`, `p="md"` |
| `Badge` status | `<Badge>` | variant `dot` ou `light` |
| `Tooltip` | `<Tooltip>` | `position="top"`, delay 300ms |

### Componentes de Layout
| Componente | Arquivo | Descrição |
|-----------|---------|-----------|
| `TopBar` | `components/TopBar.tsx` | Barra de navegação superior |
| `MetricStrip` | `components/MetricStrip.tsx` | Métricas em linha |
| `WorkspaceHealth` | `components/WorkspaceHealth.tsx` | Status do ambiente |
| `HeroCommandPanel` | `components/HeroCommandPanel.tsx` | Painel principal de comando |
| `EnvStatusBanner` | `components/EnvStatusBanner.tsx` | Banner de status de ambiente |

### Componentes de Chat/Agent
| Componente | Arquivo | Descrição |
|-----------|---------|-----------|
| `ActionRequiredCard` | `components/ActionRequiredCard.tsx` | Ação pendente do usuário |
| `ToolCallCard` | `components/ToolCallCard.tsx` | Chamada de tool em progresso |
| `ThinkingIndicator` | `components/ThinkingIndicator.tsx` | LLM processando |

## 3. Padrões de Tipografia

### Hierarquia
```tsx
// Título de página
<Title order={2} fz="xl" fw={600} c="gray.1">Título</Title>

// Subtítulo / seção
<Text fz="md" fw={500} c="gray.2">Seção</Text>

// Corpo principal
<Text fz="sm" c="gray.3">Conteúdo</Text>

// Label de form / metadata
<Text fz="xs" c="dimmed">Label</Text>

// Código / monospace
<Text fz="sm" ff="monospace" c="blue.4">código</Text>
```

### Densidades
- **Compact** (painéis de dados): `fz="xs"`, `lh={1.3}`, `gap="xs"`
- **Regular** (conteúdo geral): `fz="sm"`, `lh={1.5}`, `gap="sm"`
- **Relaxed** (onboarding, documentação): `fz="md"`, `lh={1.7}`, `gap="md"`

## 4. Estados de Componentes

Todo componente interativo deve implementar:
```
default → hover → active/pressed → focus → disabled → loading → error
```

### Padrão de Implementação
```tsx
// Sempre defina todos os estados:
const styles = {
  root: {
    transition: 'all 0.15s ease',
    '&:hover': { background: 'var(--mantine-color-dark-5)' },
    '&:active': { transform: 'scale(0.98)' },
    '&:focus-visible': { outline: '2px solid var(--mantine-color-blue-5)' },
    '&[disabled]': { opacity: 0.5, cursor: 'not-allowed' },
  }
}
```

## 5. Paleta por Contexto Funcional

| Contexto | Cor Principal | Cor de Suporte |
|----------|--------------|----------------|
| Agente / AI | `blue.5` (#4f8ef7) | `blue.3` (glow) |
| Terminal / CLI | `green.5` (#3ecf8e) | `dark-7` (bg) |
| Erro / Alerta | `red.5` (#f04e4e) | `red.9` (bg sutil) |
| Aviso / Pendente | `yellow.5` (#f5a623) | `yellow.9` (bg sutil) |
| Dados / Analytics | `purple.5` (#9b74f7) | `purple.3` (accent) |
| Sucesso / Online | `green.5` (#3ecf8e) | `green.9` (bg sutil) |
| Neutro / Inativo | `gray.5` (#5a5a6a) | `dark-6` (bg) |

## 6. Geração de Design System para Nova Feature

Ao criar uma nova feature, responda:

```
1. TIPO: Dashboard / Form / List / Chat / Settings / Onboarding?
2. DADOS PRINCIPAIS: O que o usuário precisa ver em primeiro lugar?
3. AÇÕES PRIMÁRIAS: O que o usuário faz com mais frequência?
4. ESTADOS: Quais estados de loading/error/empty existem?
5. FREQUÊNCIA DE USO: Acessa todo dia ou ocasionalmente?
```

Com base nas respostas, gere:
- Tokens específicos da feature (se necessário)
- Hierarquia de componentes (quais Mantine + quais customizados)
- Paleta de cores aplicada
- Padrão de layout (grid, sidebar, painel)
- Estados de UI necessários

## 7. Validação de Conformidade

Antes de considerar o design implementado:
- [ ] Usa apenas tokens semânticos (sem hex hardcoded no componente)
- [ ] Todos os estados de componente definidos
- [ ] Contraste de texto ≥ 4.5:1 verificado
- [ ] Dark mode consistente (zero brancos ou cinzas claros)
- [ ] CSS modules em vez de estilos inline
- [ ] Animações em transições de estado
- [ ] Responsividade definida (mesmo que só desktop)
