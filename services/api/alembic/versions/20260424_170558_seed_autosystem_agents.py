"""Seed default AutoSystem agents, skills, and user profiles."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20260424_170558"
down_revision = "20260423_223500"
branch_labels = None
depends_on = None

AUTOSYSTEM_REPO_ID = "0f94d2c0-ff90-4e09-8c52-561cd1ef27d5"
AUTOSYSTEM_CLONE_URL = (
    "https://linxpostos@dev.azure.com/linxpostos/linx-postos-autosystem/_git/autosystem3"
)
RC_AGENT_ID = "8809cf9b-0bd2-4c7c-9f7f-2e9e3b7a6d22"
PO_AGENT_ID = "ca6f9b12-b987-4d6c-a985-4ad1f8f9e31f"
EDUARDO_RC_PROFILE_ID = "369bdc95-011b-41f5-a4c4-e2fbd8dd33a7"

RC_SYSTEM_PROMPT = """Você é o agente RC/Suporte do AutoSystem.
Objetivo: levantar evidências de bugs e preparar issues claras para o time.
Você não programa, não altera arquivos e não propõe patches.
Use o repositório apenas para entender fluxo, telas, integrações, logs e nomes técnicos.
Sempre responda com sintomas, impacto, evidências necessárias, hipótese funcional e sugestão de issue.
Quando faltar dado, peça a menor informação necessária: versão, unidade, cenário, payload, tela, log ou vídeo."""

PO_SYSTEM_PROMPT = """Você é o agente PO/Analista de Sistemas do AutoSystem.
Objetivo: transformar demandas em análise funcional, regras de negócio e critérios de aceite.
Você não programa, não altera arquivos e não decide arquitetura técnica.
Use o repositório apenas para localizar comportamentos existentes, termos de domínio e impactos.
Sempre responda com contexto, atores, regra atual, regra proposta, impactos, dúvidas e critérios de aceite."""


def _skill(
    slug: str,
    title: str,
    summary: str,
    content: str,
    tags: list[str],
    agent_id: str | None = None,
) -> dict:
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"cappycloud:autosystem-skill:{slug}")),
        "agent_id": agent_id,
        "slug": slug,
        "title": title,
        "summary": summary,
        "content": content,
        "tags": tags,
    }


SKILLS = [
    _skill(
        "how-to-triar-bug-autosystem",
        "How to triage an AutoSystem bug",
        "Coleta mínima para transformar relato de bug em issue acionável.",
        """# How to triage an AutoSystem bug

1. Identifique módulo, tela, rotina, unidade, versão e usuário afetado.
2. Reproduza o caminho funcional em passos curtos, com dados de entrada e resultado esperado.
3. Procure no código nomes de telas, comandos, integrações, tabelas e mensagens para confirmar o contexto.
4. Colete evidências: print, vídeo, logs, payload, horário, filial, PDV, cupom ou documento fiscal.
5. Abra a issue com impacto, frequência, workaround, hipótese e anexos faltantes.""",
        ["autosystem", "suporte", "bug", "issue"],
        RC_AGENT_ID,
    ),
    _skill(
        "how-to-mapear-fluxo-funcional-autosystem",
        "How to map an AutoSystem functional flow",
        "Roteiro de análise funcional sem alterar código.",
        """# How to map an AutoSystem functional flow

1. Comece pelos termos usados pelo usuário e busque nomes equivalentes no repositório.
2. Mapeie entrada, processamento, saída, persistência e integrações externas.
3. Registre regras explícitas, validações, mensagens de erro e exceções de negócio.
4. Separe comportamento atual, lacunas, impacto e perguntas para negócio.
5. Finalize com critérios de aceite verificáveis e dependências conhecidas.""",
        ["autosystem", "analise", "fluxo", "regras"],
        PO_AGENT_ID,
    ),
    _skill(
        "how-to-investigar-integracao-autosystem",
        "How to investigate an AutoSystem integration",
        "Como levantar evidências de falha em integrações do AutoSystem.",
        """# How to investigate an AutoSystem integration

1. Descubra origem, destino, protocolo, payload, autenticação e rotina disparadora.
2. Diferencie falha de regra, indisponibilidade, timeout, credencial, payload inválido e rejeição externa.
3. Use logs e nomes técnicos do repositório para confirmar endpoint, serviço, fila ou arquivo envolvido.
4. Peça exemplos reais com horário, ambiente, identificador da transação e retorno completo.
5. Documente impacto operacional e próximo responsável pela validação.""",
        ["autosystem", "integracao", "suporte", "logs"],
        RC_AGENT_ID,
    ),
    _skill(
        "how-to-escrever-criterios-aceite-autosystem",
        "How to write AutoSystem acceptance criteria",
        "Modelo para critérios de aceite funcionais.",
        """# How to write AutoSystem acceptance criteria

1. Escreva cada critério como uma regra verificável pelo usuário.
2. Inclua pré-condições, ação, resultado esperado e cenários de exceção.
3. Cubra permissões, mensagens, integrações, persistência e relatórios quando aplicável.
4. Evite solução técnica; foque no comportamento observável.
5. Marque dúvidas que bloqueiam validação antes de fechar a análise.""",
        ["autosystem", "analise", "criterios", "po"],
        PO_AGENT_ID,
    ),
    _skill(
        "how-to-consultar-codigo-sem-programar",
        "How to use code as product documentation",
        "Boas práticas para consultar código sem propor implementação.",
        """# How to use code as product documentation

1. Use buscas por termos de domínio, mensagens exibidas ao usuário e nomes de tela.
2. Leia chamadas, testes e configurações para inferir comportamento existente.
3. Cite arquivos, símbolos e regras encontradas, mas não sugira patch.
4. Diferencie fato observado no código de hipótese funcional.
5. Quando o código não explicar tudo, peça evidência operacional ao usuário.""",
        ["autosystem", "codigo", "documentacao", "analise"],
    ),
]


def _upsert_agent(
    connection, agent_id: str, slug: str, name: str, description: str, icon: str, prompt: str
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO agents (id, slug, name, description, icon, system_prompt, active) "
            "VALUES (CAST(:id AS UUID), :slug, :name, :description, :icon, :prompt, TRUE) "
            "ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, "
            "icon = EXCLUDED.icon, system_prompt = EXCLUDED.system_prompt, active = TRUE, updated_at = NOW()"
        ),
        {
            "id": agent_id,
            "slug": slug,
            "name": name,
            "description": description,
            "icon": icon,
            "prompt": prompt,
        },
    )


def _insert_skill(connection, skill: dict) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO skills (id, agent_id, repository_id, slug, title, summary, content, tags, source_url, active) "
            "SELECT CAST(:id AS UUID), CAST(:agent_id AS UUID), (SELECT id FROM repositories WHERE slug = 'autosystem'), "
            "CAST(:slug AS VARCHAR), CAST(:title AS VARCHAR), CAST(:summary AS TEXT), CAST(:content AS TEXT), "
            "CAST(:tags AS TEXT[]), CAST(:source_url AS TEXT), TRUE "
            "WHERE NOT EXISTS (SELECT 1 FROM skills WHERE slug = CAST(:slug AS VARCHAR))"
        ),
        {
            "id": skill["id"],
            "agent_id": skill["agent_id"],
            "slug": skill["slug"],
            "title": skill["title"],
            "summary": skill["summary"],
            "content": skill["content"],
            "tags": skill["tags"],
            "source_url": f"autosystem://skills/{skill['slug']}",
        },
    )


def _upsert_autosystem_repository(connection) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO repositories (id, slug, name, clone_url, default_branch, sandbox_status, sandbox_path, active) "
            "VALUES (CAST(:id AS UUID), 'autosystem', 'autosystem', :clone_url, 'master', 'not_cloned', '', TRUE) "
            "ON CONFLICT (slug) DO UPDATE SET clone_url = EXCLUDED.clone_url, default_branch = EXCLUDED.default_branch, "
            "active = TRUE, updated_at = NOW()"
        ),
        {"id": AUTOSYSTEM_REPO_ID, "clone_url": AUTOSYSTEM_CLONE_URL},
    )


def upgrade() -> None:
    op.create_table(
        "user_agent_profiles",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "agent_id", sa.UUID(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("persona", sa.String(length=32), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "persona", name="uq_user_agent_profiles_user_persona"),
    )
    op.create_index("ix_user_agent_profiles_user_id", "user_agent_profiles", ["user_id"])
    op.create_index("ix_user_agent_profiles_agent_id", "user_agent_profiles", ["agent_id"])
    op.create_index("ix_user_agent_profiles_persona", "user_agent_profiles", ["persona"])
    op.create_index(
        "uq_user_agent_profiles_default_per_user",
        "user_agent_profiles",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )

    connection = op.get_bind()
    _upsert_autosystem_repository(connection)
    _upsert_agent(
        connection,
        RC_AGENT_ID,
        "rc-suporte-autosystem",
        "RC/Suporte AutoSystem",
        "Triagem de bugs, coleta de evidências e abertura de issue para o AutoSystem.",
        "support_agent",
        RC_SYSTEM_PROMPT,
    )
    _upsert_agent(
        connection,
        PO_AGENT_ID,
        "po-analista-autosystem",
        "PO/Analista AutoSystem",
        "Análise funcional, impacto e critérios de aceite para o AutoSystem.",
        "fact_check",
        PO_SYSTEM_PROMPT,
    )

    for skill in SKILLS:
        _insert_skill(connection, skill)

    connection.execute(
        sa.text(
            "INSERT INTO user_agent_profiles (id, user_id, agent_id, persona, is_default) "
            "SELECT CAST(:profile_id AS UUID), u.id, a.id, 'rc', TRUE "
            "FROM users u JOIN agents a ON a.slug = 'rc-suporte-autosystem' "
            "WHERE u.email = 'eduardocecon@gmail.com' "
            "ON CONFLICT (user_id, persona) DO UPDATE SET agent_id = EXCLUDED.agent_id, "
            "is_default = TRUE, updated_at = NOW()"
        ),
        {"profile_id": EDUARDO_RC_PROFILE_ID},
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM skills WHERE slug = ANY(CAST(:slugs AS TEXT[]))"),
        {"slugs": [skill["slug"] for skill in SKILLS]},
    )
    connection.execute(
        sa.text(
            "DELETE FROM user_agent_profiles WHERE agent_id IN (CAST(:rc_id AS UUID), CAST(:po_id AS UUID))"
        ),
        {"rc_id": RC_AGENT_ID, "po_id": PO_AGENT_ID},
    )
    connection.execute(
        sa.text(
            "DELETE FROM agents WHERE slug IN ('rc-suporte-autosystem', 'po-analista-autosystem')"
        )
    )
    op.drop_index("uq_user_agent_profiles_default_per_user", table_name="user_agent_profiles")
    op.drop_index("ix_user_agent_profiles_persona", table_name="user_agent_profiles")
    op.drop_index("ix_user_agent_profiles_agent_id", table_name="user_agent_profiles")
    op.drop_index("ix_user_agent_profiles_user_id", table_name="user_agent_profiles")
    op.drop_table("user_agent_profiles")
