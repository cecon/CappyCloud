# Spec: vários times no filtro e filtro por time nas conversas

Pedido do Rodolfo (PROTHEUS-azure), 18/11/2026, depois da 015 (times no relatório).

## Histórias

- **US1:** Em Admin → Relatórios, o filtro de time aceita mais de um time ao mesmo tempo, por exemplo PROTHEUS PRIME SP + PROTHEUS PRIME ÁGIL. Com nada marcado, entram todos os times. "Sem time" também pode ser marcado junto com outros.
- **US2:** Em Admin → Conversas, há um filtro por time igual ao do relatório. A lista mostra o time da pessoa em cada conversa.

## Regras

- A API recebe `team` repetido (`?team=A&team=B`). Um único `team`, como antes, continua valendo.
- Os nomes são comparados sem diferenciar maiúsculas. Espaços extras e repetidos são ignorados, e o máximo é 50 times por filtro.
- `__none__` significa sem time: a pessoa não tem time no workspace da conversa.
- `filters.team` (texto) da resposta do relatório vira `filters.teams` (lista). O único cliente é o web.
- Exportação: o Resumo mostra os times escolhidos separados por vírgula, ou "Todos".

## Fora do escopo

- Guardar o filtro escolhido entre sessões.
