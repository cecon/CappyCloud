---
name: ux-design
description: Use esta habilidade quando precisar tomar decisões de UX/UI no CappyCloud — escolher padrões de componentes, estilos visuais, fluxos de interação, acessibilidade e micro-animações. Cobre React 19 + Mantine 9 com tema dark mode estilo IDE premium.
---

# UX Design Intelligence — CappyCloud

Motor de raciocínio de design para o CappyCloud. Toda decisão visual deve partir daqui antes de implementar.

## 1. Identidade Visual

**Tema**: "The Silent Architect" — IDE premium, dark mode.

| Token | Valor | Uso |
|-------|-------|-----|
| Background primário | `#0d0d0f` | Superfícies principais |
| Background secundário | `#141417` | Cards, painéis |
| Background elevado | `#1a1a1f` | Modais, dropdowns |
| Borda sutil | `#2a2a32` | Separadores, bordas |
| Texto primário | `#e8e8ed` | Headings, labels |
| Texto secundário | `#7a7a8a` | Subtext, placeholders |
| Accent azul | `#4f8ef7` | CTAs primários, links |
| Accent verde | `#3ecf8e` | Sucesso, status online |
| Accent vermelho | `#f04e4e` | Erro, destrutivo |
| Accent amarelo | `#f5a623` | Aviso, pendente |

**Tipografia**: Sistema nativo do Mantine. Use `fz` props: `xs`/`sm`/`md`/`lg`/`xl`. Nunca hardcode `px`.

## 2. Padrões de Componentes Mantine

### Inputs e Forms
```tsx
// Sempre dark-aware, sem background branco
<TextInput
  styles={{ input: { background: 'var(--mantine-color-dark-7)', borderColor: 'var(--mantine-color-dark-4)' } }}
/>
```
- Validação inline: use `error` prop — nunca toast para erros de campo
- Labels sempre presentes (acessibilidade)
- Placeholder em `--mantine-color-dark-3`

### Cards e Painéis
```tsx
<Paper p="md" radius="md" withBorder style={{ borderColor: 'var(--mantine-color-dark-4)' }}>
```
- `withBorder` sempre — evita cards "flutuantes" sem delimitação
- `radius="md"` padrão (8px)
- `p="md"` ou `p="lg"` — nunca `p="xs"` em containers principais

### Tabelas e Listas de Dados
- Use `<Table striped highlightOnHover>` do Mantine
- Colunas: máximo 6 visíveis; demais em painel lateral ou expandível
- Estado vazio: sempre um `<EmptyState>` component, nunca lista em branco
- Paginação: use `<Pagination>` — nunca scroll infinito em tabelas admin

### Modais e Drawers
- Ações destrutivas: sempre `<Modal>` com confirmação explícita
- Formulários complexos (>4 campos): `<Drawer>` lateral, não modal
- `<Modal size="md">` padrão; `"xl"` apenas para visualizações de conteúdo

### Feedback e Notificações
- Erros de API: `notifications.show({ color: 'red', ... })` via Mantine Notifications
- Sucesso de ação: notificação de 3s, sem interrupção de fluxo
- Loading: `<Loader size="sm" color="blue">` inline; `<Skeleton>` para placeholders de conteúdo
- Estados de erro de página inteira: componente `<ErrorBoundary>` com retry

## 3. Padrões de Layout

### Hierarquia de Espaçamento
```
gap="xs"  → 8px   (itens relacionados: ícone + label)
gap="sm"  → 12px  (elementos dentro de um card)
gap="md"  → 16px  (seções dentro de uma página)
gap="lg"  → 24px  (grupos de seções)
gap="xl"  → 32px  (separação entre blocos principais)
```

### Grid de Página
- Sidebar: largura fixa `260px`
- Conteúdo principal: `flex: 1`, `min-width: 0` (evita overflow)
- Painel lateral de detalhes: `320px`–`400px`
- Nunca use porcentagens para larguras de painel — use `px` ou `rem`

### Responsividade
- Mobile-first apenas para páginas públicas (login, landing)
- Dashboard e páginas admin: `min-width: 1024px` — é uma ferramenta profissional
- Use `<Stack>` em mobile, `<Group>` em desktop via `visibleFrom`/`hiddenFrom`

## 4. Micro-interações e Animações

**Regra**: animações devem ser imperceptíveis individualmente, mas sentidas como fluidez geral.

```css
/* Transição padrão para hover/active */
transition: all 0.15s ease;

/* Fade-in de conteúdo carregado */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}
animation: fadeIn 0.2s ease;

/* Pulse para indicadores de loading */
animation: pulse 1.5s ease-in-out infinite;
```

- Hover em botões: `scale(1.02)` + `brightness(1.1)` — nunca só cor
- Clique: `scale(0.98)` de 80ms
- Abertura de modal: `transform: scale(0.95) → 1.0` em 150ms
- Nunca use `animation-duration > 300ms` em interações diretas do usuário

## 5. Acessibilidade

- Contraste mínimo: 4.5:1 para texto normal, 3:1 para texto grande
- Todos os ícones interativos: `aria-label` obrigatório
- Focus visible: nunca `outline: none` sem substituto visual
- Ordem de tab: lógica e sequencial — teste navegando só com teclado
- `<ActionIcon>` sempre com `title` prop para tooltip de acessibilidade

## 6. Anti-Patterns a Evitar

| Evitar | Usar em vez |
|--------|------------|
| Cores hardcoded (`#fff`, `#000`) | Variáveis CSS do Mantine |
| `position: absolute` para layout | Flexbox/Grid |
| `!important` em CSS | Especificidade adequada |
| Modais em cascata (modal dentro de modal) | Drawer ou página dedicada |
| Spinner de página inteira em recargas parciais | Skeleton por seção |
| Toast para erro de validação de campo | `error` prop inline |
| Botões sem estado de loading | `loading` prop do Mantine |
| Tabela sem estado vazio | Componente EmptyState |

## 7. Fluxo de Decisão

```
Nova interface/componente?
  ├── Existe componente Mantine para isso? → Use com customização mínima
  ├── Precisa de composição? → Combine componentes Mantine
  └── Precisa de algo novo? → Construa sobre primitivos Mantine (Box, Flex)

Decisão de cor?
  ├── Status/feedback → Use cores semânticas (success/error/warning)
  ├── Interação principal → Accent azul (#4f8ef7)
  └── Conteúdo → Texto primário/secundário conforme hierarquia

Layout?
  ├── Lista de dados → Table + Pagination
  ├── Formulário longo → Drawer lateral
  ├── Confirmação → Modal pequeno
  └── Dashboard → Grid com MetricStrip + Cards
```

## 8. Checklist Pré-entrega

- [ ] Dark mode funcionando sem nenhum branco/cinza claro visível
- [ ] Todos os estados: loading, error, empty, filled
- [ ] Hover e focus visíveis em todos os elementos interativos
- [ ] Sem texto hardcoded — use variáveis de cor do Mantine
- [ ] Animações presentes em transições de estado
- [ ] `aria-label` em todos os ícones sem texto adjacente
- [ ] Testado com `code-review` após implementação
