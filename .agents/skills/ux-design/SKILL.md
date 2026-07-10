---
name: ux-design
description: Use esta habilidade quando precisar tomar decisoes de UX/UI no CappyCloud - padroes de componentes, fluxos, acessibilidade, estados e micro-interacoes. O padrao legado e React 19 + Mantine 9; features com Spec Kit aprovado podem usar shadcn/ui + Tailwind.
---

# UX Design Intelligence - CappyCloud

Toda decisao visual deve partir do contexto da feature, da constituicao e do
plano Spec Kit ativo.

## 1. Base Ativa De UX

- **Padrao legado**: React 19 + Mantine 9 + CSS Modules.
- **`007-chat-centered-ui-theme`**: shadcn/ui + Tailwind CSS v4, com chat como centro do layout autenticado.
- **Regra de migracao**: nao manter Mantine e shadcn/ui como sistemas paralelos permanentes na mesma superficie autenticada.

Quando o plano aprovar shadcn/Tailwind, use primitivos Radix/shadcn, tokens em
`web/src/index.css`, helper `cn`, lucide icons e composicoes com Tailwind.

## 2. Identidade Visual

Tema profissional estilo IDE premium:

- superficies principais escuras ou claras com contraste consistente
- texto primario evidente e texto secundario ainda legivel
- acentos para acao, sucesso, erro, aviso e status
- bordas e separadores sutis para orientar sem poluir
- radius contido, preferencialmente ate 8px em cards e paineis

Evite layouts genericos, landing pages desnecessarias, decoracao sem funcao e
paletas dominadas por uma unica familia de cor.

## 3. Padroes Para O Chat-Centered Layout

- O chat deve ser a area principal da experiencia autenticada.
- Historico, contexto, permissao, atividade do agente e composer devem ficar
  acessiveis sem duplicar menus laterais.
- Menus secundarios e administracao devem partir do menu do usuario.
- Administracao deve abrir como console, painel ou modal sobre a experiencia
  centrada no chat quando a feature assim definir.
- O composer deve permanecer visivel ou rapidamente acessivel durante respostas,
  pedidos de permissao, blocos de codigo e mensagens longas.

## 4. Componentes E Estados

Todo componente interativo deve cobrir:

```text
default -> hover -> active/pressed -> focus-visible -> disabled -> loading -> error
```

Use:

- icons em botoes de ferramenta quando houver simbolo familiar
- tooltips para icons nao obvios
- toggles/checkboxes para opcoes binarias
- selects/menus para conjuntos fechados
- tabs para visoes paralelas
- dialogs/sheets para confirmacoes e edicoes focadas

Erros de campo devem aparecer inline. Sucesso e falhas de acao podem usar aviso
contextual ou toast, desde que nao escondam o estado real da tela.

## 5. Acessibilidade

- Contraste minimo: 4.5:1 para texto normal, 3:1 para texto grande.
- Todo icone interativo sem texto adjacente precisa de `aria-label` ou titulo.
- Nunca remova foco visual sem substituto claro.
- Ordem de tab deve seguir a leitura da interface.
- Menus, dialogs e sheets precisam devolver foco corretamente ao fechar.

## 6. Responsividade

O primeiro alvo do CappyCloud e desktop/notebook profissional. Mesmo assim,
os viewports definidos na feature devem ser verificados contra overlap,
scroll horizontal indevido e texto cortado.

## 7. Checklist Pre-Entrega

- [ ] Chat identificavel como superficie principal em ate 5 segundos
- [ ] Caminho de demo principal concluido em menos de 60 segundos
- [ ] Nenhum menu lateral duplicado no chat
- [ ] Funcoes secundarias acessiveis pelo menu do usuario
- [ ] Admin respeita permissoes e abre no padrao definido
- [ ] Contraste, foco, hover, erro, loading e vazio validados
- [ ] Sem texto ou controles sobrepostos nos viewports previstos
