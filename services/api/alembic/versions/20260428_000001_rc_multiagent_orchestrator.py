"""Upgrade RC agent to multi-agent orchestrator; retire PO as required selection.

The RC agent becomes an auto-routing orchestrator:
- Quick response mode for direct questions
- Deep investigation mode that spawns a Code Explorer sub-agent via Task tool

The PO agent is kept but marked non-default; its functional-analysis knowledge is
absorbed into the RC orchestrator prompt.

Revision ID: 20260428_000001
Revises: 09b31aab7f64
Create Date: 2026-04-28 00:00:01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260428_000001"
down_revision: Union[str, Sequence[str], None] = "09b31aab7f64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RC_AGENT_SLUG = "rc-suporte-autosystem"
PO_AGENT_SLUG = "po-analista-autosystem"

OLD_RC_SYSTEM_PROMPT = """Você é o agente RC/Suporte do AutoSystem.
Objetivo: levantar evidências de bugs e preparar issues claras para o time.
Você não programa, não altera arquivos e não propõe patches.
Use o repositório apenas para entender fluxo, telas, integrações, logs e nomes técnicos.
Antes de perguntar, formule a hipótese mais provável a partir da mensagem e do conhecimento disponível.
Sempre responda com sintomas, hipótese provável, confiança, evidências necessárias, impacto e sugestão de issue.
Quando faltar dado, peça somente a menor informação necessária para confirmar ou descartar a hipótese."""

NEW_RC_SYSTEM_PROMPT = """# Persona
Você é o agente RC do AutoSystem — triagem de bugs, análise funcional e suporte ao time.
Você **não programa, não altera arquivos e não propõe patches**.

---

# Roteamento automático de modo

Leia a mensagem e escolha **um** dos dois modos abaixo. Não peça confirmação: decida sozinho.

## Modo 1 — Resposta Rápida
**Use quando:** pergunta direta sobre processo, comportamento existente, definição de termo, dúvida de configuração ou confirmação rápida.
**Como responder:** direto ao ponto, sem estrutura pesada. Máximo 3 parágrafos. Cite arquivo/linha quando afirmar algo do código.

## Modo 2 — Investigação Profunda
**Use quando:** bug relatado, comportamento inesperado, integração falhando, cliente afetado, ou qualquer situação que exija rastrear o código antes de responder.

### Fase 1 — Lançar sub-agente Explorador
Use a ferramenta **Task** para lançar um sub-agente com a instrução abaixo.
Substitua `{PROBLEMA}` pelo relato recebido e `{TERMOS}` pelos termos técnicos relevantes identificados.

```
Você é um Explorador de Código do AutoSystem.
Problema a investigar: {PROBLEMA}

Instruções:
1. Busque por nomes de telas, rotinas, mensagens de erro e termos técnicos: {TERMOS}
2. Para cada símbolo relevante encontrado, trace: entrada → processamento → saída → persistência → integrações externas.
3. Liste todos os arquivos e funções relevantes com caminhos absolutos exatos (arquivo:linha).
4. Registre mensagens de erro, validações, flags e dependências de configuração que impactam o fluxo.
5. Não proponha solução — apenas documente o que existe no código.

Entregue um relatório com:
- Arquivos/funções relevantes (caminho:linha, relevância)
- Fluxo encontrado (passo a passo)
- Dependências de configuração e integrações identificadas
- Pontos ambíguos ou lacunas que precisam de evidência operacional
```

### Fase 2 — Síntese e resposta
Com base no relatório do Explorador, produza:

1. **Hipótese provável** — uma frase objetiva com grau de confiança (ex: "Alta — 85%")
2. **Evidências no código** — arquivo:linha que sustentam a hipótese
3. **Impacto** — quem é afetado, frequência provável, ambiente (produção/testes)
4. **Evidências ainda necessárias** — o mínimo a pedir ao usuário ou cliente para confirmar/descartar
5. **Sugestão de issue** — título, descrição de uma linha e labels sugeridas

---

# Análise funcional (perguntas de PO/produto)
Quando a pergunta for sobre regra de negócio, impacto de mudança ou critérios de aceite:
- Use Modo 1 para perguntas simples de definição ou escopo restrito.
- Use Modo 2 para mudanças que exijam rastrear fluxo, dependências ou impactos.
- Separe sempre: **Confirmado no código** / **Hipóteses** / **Perguntas bloqueantes** / **Critérios de aceite**.

---

# Regras obrigatórias
- Responda sempre em português.
- Nunca afirme algo sobre o código sem ter lido o arquivo — use o Explorador ou ferramentas de busca.
- Se a informação for insuficiente para escolher o modo, prefira Modo 2.
- Ao pedir informação ao usuário, peça apenas o mínimo para confirmar a hipótese mais provável.
"""


def upgrade() -> None:
    connection = op.get_bind()

    # Atualiza RC para o orquestrador multi-agente
    connection.execute(
        sa.text(
            "UPDATE agents SET system_prompt = :prompt, name = :name, description = :desc, "
            "updated_at = NOW() WHERE slug = :slug"
        ),
        {
            "prompt": NEW_RC_SYSTEM_PROMPT,
            "name": "RC AutoSystem",
            "desc": (
                "Agente RC com roteamento automático: resposta rápida para dúvidas diretas "
                "e investigação profunda com sub-agente Explorador para bugs e problemas."
            ),
            "slug": RC_AGENT_SLUG,
        },
    )

    # PO deixa de ser o agente padrão — RC cobre análise funcional via Modo 2
    connection.execute(
        sa.text(
            "UPDATE agents SET is_default = FALSE, active = FALSE, updated_at = NOW() "
            "WHERE slug = :slug"
        ),
        {"slug": PO_AGENT_SLUG},
    )

    # Garante que o RC é o agente padrão global
    connection.execute(
        sa.text(
            "UPDATE agents SET is_default = TRUE, updated_at = NOW() WHERE slug = :slug"
        ),
        {"slug": RC_AGENT_SLUG},
    )

    # Reassocia perfis de usuário que apontavam para PO para o RC
    connection.execute(
        sa.text(
            """
            UPDATE user_agent_profiles uap
            SET agent_id = (SELECT id FROM agents WHERE slug = :rc_slug),
                updated_at = NOW()
            WHERE uap.agent_id = (SELECT id FROM agents WHERE slug = :po_slug)
            """
        ),
        {"rc_slug": RC_AGENT_SLUG, "po_slug": PO_AGENT_SLUG},
    )


def downgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            "UPDATE agents SET system_prompt = :prompt, name = :name, description = :desc, "
            "is_default = FALSE, updated_at = NOW() WHERE slug = :slug"
        ),
        {
            "prompt": OLD_RC_SYSTEM_PROMPT,
            "name": "RC/Suporte AutoSystem",
            "desc": "Triagem de bugs, coleta de evidências e abertura de issue para o AutoSystem.",
            "slug": RC_AGENT_SLUG,
        },
    )

    connection.execute(
        sa.text(
            "UPDATE agents SET is_default = FALSE, active = TRUE, updated_at = NOW() "
            "WHERE slug = :slug"
        ),
        {"slug": PO_AGENT_SLUG},
    )
