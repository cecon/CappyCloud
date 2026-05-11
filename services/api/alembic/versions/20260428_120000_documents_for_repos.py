"""documents_for_repos

Adiciona suporte a documentos de referência por repositório (RAG de suporte):

  - documents              tabela com metadados da fonte (PDF/XLSX/URL/texto),
                           checksum, versão e status de indexação.
  - skills.document_id     FK opcional para ``documents`` — quando preenchida,
                           a skill é um *chunk* de um documento (não uma skill
                           "de agente"). ON DELETE CASCADE para limpar chunks
                           ao remover/reindexar o documento.
  - skills.chunk_index     ordem do chunk dentro do documento (apenas info).

Os chunks reutilizam a tabela ``skills`` (já com embedding + repository_id),
o que permite que o RAG existente (`/skills/_search/internal`) também encontre
conteúdo de documentos sem nova infra de busca.

Revision ID: 20260428_120000
Revises: 20260428_000001
Create Date: 2026-04-28 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260428_120000"
down_revision: Union[str, Sequence[str], None] = "20260428_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.UUID(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("chunks_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_repository_id", "documents", ["repository_id"])
    op.create_index("ix_documents_status", "documents", ["status"])

    op.add_column("skills", sa.Column("document_id", sa.UUID(), nullable=True))
    op.add_column("skills", sa.Column("chunk_index", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_skills_document",
        "skills",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_skills_document_id", "skills", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_skills_document_id", table_name="skills")
    op.drop_constraint("fk_skills_document", "skills", type_="foreignkey")
    op.drop_column("skills", "chunk_index")
    op.drop_column("skills", "document_id")

    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_repository_id", table_name="documents")
    op.drop_table("documents")
