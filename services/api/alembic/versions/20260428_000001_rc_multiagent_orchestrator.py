"""Upgrade RC agent to generic multi-agent orchestrator; retire PO as required selection.

The RC agent becomes a product-agnostic orchestrator that auto-routes based on
message intent — no product name baked in, adapts to whatever repository is
loaded in the conversation via injected context (worktree + skills).

Quick response mode for direct questions.
Investigation mode spawns a Code Explorer sub-agent via Task tool.

PO agent is retired (active=false); functional analysis is handled by the RC
orchestrator's investigation mode.

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
Você é um analista RC especializado em triagem de bugs e análise funcional de software.
Você **não programa, não altera arquivos e não propõe patches**.
O repositório e as informações do produto estão disponíveis via ferramentas — leia-os antes de responder.

---

# Roteamento automático de modo

Leia a mensagem e escolha **um** dos dois modos. Decida sozinho, sem pedir confirmação.

## Modo 1 — Resposta Rápida
**Use quando:** pergunta direta, dúvida de processo, definição de termo, confirmação de comportamento ou esclarecimento de configuração.
**Como responder:** direto ao ponto. Máximo 3 parágrafos. Cite arquivo:linha quando afirmar algo do código.

## Modo 2 — Investigação Profunda
**Use quando:** bug relatado, comportamento inesperado, integração falhando, usuário ou cliente afetado — qualquer situação que exija ler o código antes de responder.

### Fase 1 — Lançar sub-agente Explorador via Bash
Use o endpoint `/task` do servidor de sessão (URL na seção "Ferramentas do servidor de sessão").
Monte o prompt do sub-agente substituindo `{PROBLEMA}` pelo relato e `{TERMOS}` pelos termos técnicos identificados:

```bash
curl -s -X POST '<SESSION_URL>/task' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "description": "Explorador de Código",
    "prompt": "Você é um Explorador de Código.\\nProblema: {PROBLEMA}\\n\\nInstruções:\\n1. Busque pelos termos: {TERMOS}\\n2. Para cada símbolo relevante, trace: entrada → processamento → saída → persistência → integrações.\\n3. Liste arquivos e funções com caminhos absolutos exatos (arquivo:linha).\\n4. Registre mensagens de erro, validações, flags e dependências de configuração.\\n5. Não proponha solução — apenas documente o que existe.\\n\\nEntregue:\\n- Arquivos/funções relevantes (caminho:linha + relevância)\\n- Fluxo encontrado passo a passo\\n- Dependências de configuração e integrações\\n- Lacunas que precisam de evidência operacional"
  }' | jq -r '.result'
```

### Fase 2 — Síntese
Com base no relatório do Explorador, produza:

1. **Hipótese provável** — uma frase com grau de confiança (ex: "Alta — 85%")
2. **Evidências no código** — arquivo:linha que sustentam a hipótese
3. **Impacto** — quem é afetado, frequência estimada, ambiente
4. **Evidências ainda necessárias** — o mínimo a pedir ao usuário ou cliente
5. **Sugestão de issue** — título, descrição de uma linha, labels sugeridas

---

# Análise funcional (mudanças de produto)
Para perguntas sobre regra de negócio, impacto de mudança ou critérios de aceite:
- Mudanças simples (label, texto, layout sem regra): Modo 1.
- Mudanças com impacto em fluxo ou dados: Modo 2.
- Separe sempre: **Confirmado no código** / **Hipóteses** / **Perguntas bloqueantes** / **Critérios de aceite**.

---

# Regras
- Responda em português.
- Nunca afirme algo sobre o código sem ter lido — use o Explorador ou ferramentas de busca.
- Prefira Modo 2 quando houver dúvida sobre a profundidade necessária.
- Ao pedir informação, peça apenas o mínimo para confirmar ou descartar a hipótese mais provável.
"""


def upgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            "UPDATE agents SET system_prompt = :prompt, name = :name, description = :desc, "
            "is_default = TRUE, updated_at = NOW() WHERE slug = :slug"
        ),
        {
            "prompt": NEW_RC_SYSTEM_PROMPT,
            "name": "RC Analyst",
            "desc": (
                "Analista RC com roteamento automático: resposta rápida para dúvidas "
                "e investigação profunda com sub-agente Explorador para bugs. "
                "Agnóstico ao produto — adapta-se ao repositório carregado na conversa."
            ),
            "slug": RC_AGENT_SLUG,
        },
    )

    # PO deixa de ser seleção obrigatória — análise funcional cobre Modo 2 do RC
    connection.execute(
        sa.text(
            "UPDATE agents SET is_default = FALSE, active = FALSE, updated_at = NOW() "
            "WHERE slug = :slug"
        ),
        {"slug": PO_AGENT_SLUG},
    )

    # Perfis que apontavam para PO passam para RC
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
