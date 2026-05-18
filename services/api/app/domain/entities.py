"""Domain entities — pure Python dataclasses, no ORM or framework imports."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UserRole(StrEnum):
    """Papel do utilizador no controlo de acesso.

    Valores são strings persistidas em BD (lower-case), seguindo ADR-005.
    ``ADMIN`` ignora tabelas de acesso (vê tudo); ``USER`` só acessa o que
    lhe é atribuído explicitamente (sandboxes, repositórios, modelos).
    """

    ADMIN = "admin"
    USER = "user"


class SandboxRuntime(StrEnum):
    """Orquestrador de containers usado para uma sandbox (ADR-004 §8).

    ``COMPOSE`` é a única implementação completa hoje. ``SWARM`` é stub
    até que o adapter de produção seja implementado.
    """

    COMPOSE = "compose"
    SWARM = "swarm"


class ContainerStatus(StrEnum):
    """Estado do container no orquestrador (ADR-004 §3).

    Independente do ``status`` lógico (active|draining|offline) — este
    descreve o ciclo de vida físico do container, não o uso dele.
    """

    NOT_CREATED = "not_created"
    STARTING = "starting"
    RUNNING = "running"
    CONFIGURING = "configuring"
    CONFIGURED = "configured"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class User:
    id: uuid.UUID
    email: str
    hashed_password: str
    role: UserRole = UserRole.USER
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN


@dataclass
class Sandbox:
    """Container sandbox hospedando openclaude gRPC + session_server HTTP.

    Após ADR-004, a sandbox é entidade cadastrável que descreve uma instância
    a ser orquestrada (Docker Compose ou Swarm). Campos:

    - ``runtime``: qual adapter usa para criar/iniciar o container.
    - ``image``: imagem Docker.
    - ``env_vars``: variáveis injetadas no container (não-sensíveis).
    - ``container_status``: estado físico do container no orquestrador.
    - ``status``: estado lógico (uso), independente.
    """

    id: uuid.UUID
    name: str
    host: str
    grpc_port: int = 50051
    session_port: int = 8080
    status: str = "active"  # active | draining | offline (lógico)
    runtime: SandboxRuntime = SandboxRuntime.COMPOSE
    image: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    container_status: ContainerStatus = ContainerStatus.NOT_CREATED
    register_token: str | None = None
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class GitProvider:
    """Provedor de repositórios git com credenciais criptografadas."""

    id: uuid.UUID
    name: str
    provider_type: str  # github | azure_devops | gitlab | bitbucket
    base_url: str = ""
    org_or_project: str = ""
    token_encrypted: str = ""
    active: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class AiProvider:
    """Provedor de modelos IA (OpenRouter, Anthropic, OpenAI…)."""

    id: uuid.UUID
    name: str
    base_url: str = "https://openrouter.ai/api/v1"
    api_key_encrypted: str = ""
    active: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class AiModel:
    """Modelo IA com capabilities, preços e flags de default por capability.

    capabilities: ['text', 'vision', 'embedding', 'video']
    is_default:   {'text': True, 'vision': False, ...}
    Preços em USD por **1 milhão** de tokens (formato OpenRouter normalizado).
    """

    id: uuid.UUID
    provider_id: uuid.UUID
    model_id: str
    display_name: str
    capabilities: list[str] = field(default_factory=lambda: ["text"])
    is_default: dict = field(default_factory=dict)
    context_window: int = 200000
    input_cost_per_1m_usd: float | None = None
    output_cost_per_1m_usd: float | None = None
    active: bool = True
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class Repository:
    """Repositório git com estado de sincronização no sandbox.

    sandbox_status: not_cloned | cloning | cloned | error
    """

    id: uuid.UUID
    slug: str
    name: str
    clone_url: str
    default_branch: str = "main"
    confluence_url: str = ""
    confluence_space: str = ""
    provider_id: uuid.UUID | None = None
    sandbox_id: uuid.UUID | None = None
    sandbox_status: str = "not_cloned"
    sandbox_path: str = ""
    last_sync_at: datetime | None = None
    error_message: str | None = None
    signoz_service_name: str | None = None
    active: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class SandboxSyncItem:
    """Item na fila de sincronização DB → sandbox VM.

    operation: clone_repo | remove_repo | update_git_auth | reconfigure_model
    status:    pending | processing | done | error
    """

    id: uuid.UUID
    sandbox_id: uuid.UUID
    operation: str
    payload: dict = field(default_factory=dict)
    priority: int = 5
    status: str = "pending"
    retries: int = 0
    last_error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    processed_at: datetime | None = None


# ── Conversations ─────────────────────────────────────────────


@dataclass
class RepoEnvironment:
    id: uuid.UUID
    slug: str
    name: str
    repo_url: str
    branch: str = "main"
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class Conversation:
    """Thread de conversa com rastreamento completo de sessão, PR e CI."""

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    # Infra
    sandbox_id: uuid.UUID | None = None
    ai_model_id: uuid.UUID | None = None
    # Multi-repo session
    repos: list[dict] = field(default_factory=list)
    session_root: str | None = None
    # Worktree state
    worktree_exists: bool = False
    lines_added: int = 0
    lines_removed: int = 0
    files_changed: int = 0
    # PR tracking
    pr_url: str | None = None
    pr_status: str = "none"  # none | open | draft | merged | closed
    pr_approved: bool = False
    pr_number: int | None = None
    github_repo_slug: str | None = None
    # CI tracking
    ci_status: str = "unknown"  # unknown | pending | running | passed | failed
    ci_url: str | None = None


@dataclass
class Message:
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime = field(default_factory=_utcnow)
    # Uso por turno — preenchido apenas em mensagens do assistente.
    model_used: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class MessageAttachment:
    """Anexo (imagem inicialmente) carregado pelo utilizador numa conversa.

    O bytes vivem num storage separado (volume Docker / S3); aqui só metadado
    + ``vision_description``: o texto produzido por um modelo de visão que é
    injetado no prompt do agente para permitir que modelos text-only raciocinem
    sobre o conteúdo da imagem.
    """

    id: uuid.UUID
    conversation_id: uuid.UUID
    mime_type: str
    storage_path: str
    original_filename: str
    size_bytes: int = 0
    kind: str = "image"
    message_id: uuid.UUID | None = None
    vision_description: str | None = None
    vision_model_used: str | None = None
    uploaded_by: uuid.UUID | None = None
    uploaded_at: datetime = field(default_factory=_utcnow)


# ── MCP (Model Context Protocol) ─────────────────────────────


@dataclass
class SandboxSkill:
    """Skill *global* por sandbox (ADR-004 §6).

    Materializada em ``~/.claude/skills/<name>/SKILL.md`` no container ao boot.
    Não confundir com ``Skill`` (por repositório, RAG) em
    ``orm_models_agent.py`` — essa é injetada por worktree, não por sandbox.

    ``name`` é único por (sandbox, name) e vira o slug da pasta.
    """

    id: uuid.UUID
    sandbox_id: uuid.UUID
    name: str  # slug; vira o nome da pasta em ~/.claude/skills/
    description: str = ""
    content: str = ""  # markdown que vira o corpo do SKILL.md
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class SandboxAgent:
    """Subagente *global* por sandbox (ADR-004 §6).

    Materializado em ``~/.claude/agents/<name>.md`` com frontmatter YAML
    contendo ``name``, ``description``, ``tools``, ``model``; o corpo é o
    ``system_prompt``.

    ``name`` é único por (sandbox, name).
    """

    id: uuid.UUID
    sandbox_id: uuid.UUID
    name: str  # slug; vira o nome do arquivo <name>.md
    description: str = ""
    system_prompt: str = ""
    model: str = ""  # ex: "claude-opus-4-7" — opcional, vai como frontmatter
    tools: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class McpServer:
    """Servidor MCP configurado por sandbox (ADR-004 §6).

    Mapeia para uma entrada em ``mcpServers`` no ``~/.claude/settings.json``
    do openclaude rodando dentro do container da sandbox. Como o container é
    compartilhado por todos os utilizadores autorizados, a configuração de
    MCP é por sandbox, não por utilizador. Apenas ADMINs gerenciam.

    ``name`` é único por (sandbox, name) e vira a chave em ``mcpServers``.
    """

    id: uuid.UUID
    sandbox_id: uuid.UUID
    name: str  # chave única por sandbox (ex: "github", "filesystem")
    command: str  # ex: "npx", "uvx", "python"
    args: list[str] = field(default_factory=list)  # ex: ["-y", "@mcp/server-github"]
    env: dict = field(default_factory=dict)  # ex: {"GITHUB_TOKEN": "..."}
    enabled: bool = True
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
