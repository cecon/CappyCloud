---
name: global
description: Padrões globais, naming conventions, arquitetura hexagonal, tratamento de erros e estrutura de projeto — válido para todos os repositórios e agentes.
---

# Global Patterns

Referência compartilhada de padrões e convenções aplicáveis a **todos os projetos e agentes**. Use quando precisar aplicar consistência em código, estrutura de projeto, naming conventions, ou validar conformidade com arquitetura hexagonal.

## 1. Padrões Globais de Naming

### Python (Backend)
| Conceito | Padrão | Exemplo |
|----------|--------|---------|
| Arquivo de domínio | snake_case | `user_repository.py` |
| Classe | PascalCase | `UserRepository`, `CreateUserUseCase` |
| Função/método | snake_case | `fetch_user()`, `is_valid()` |
| Constante | SCREAMING_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Enum | PascalCase (classe), SCREAMING_SNAKE_CASE (valor) | `class Status(str, Enum): ACTIVE = "active"` |
| Porta (ABC) | `<Entity>Repository` ou `<Entity>Service` | `UserRepository`, `EmailService` |
| Use Case | `<Verb><Entity>UseCase` | `CreateUserUseCase`, `FetchUserByIdUseCase` |

### TypeScript/React (Frontend)
| Conceito | Padrão | Exemplo |
|----------|--------|---------|
| Arquivo | kebab-case (componente) ou snake_case (utils) | `user-card.tsx`, `api_client.ts` |
| Componente React | PascalCase | `UserCard`, `ChatContainer` |
| Função/hook | camelCase ou `use*` | `fetchUser()`, `useUserData()` |
| Constante | SCREAMING_SNAKE_CASE | `MAX_MESSAGE_LENGTH` |
| Type/Interface | PascalCase | `User`, `ChatMessage` |

### SQL/Database
| Conceito | Padrão | Exemplo |
|----------|--------|---------|
| Tabela | snake_case (plural) | `users`, `chat_sessions` |
| Coluna | snake_case | `first_name`, `created_at` |
| Índice | `idx_<table>_<column>` | `idx_users_email` |
| Constraint | `fk_<table>_<referenced_table>` | `fk_messages_user_id` |
| Enum | SCREAMING_SNAKE_CASE | `ROLE_ADMIN`, `STATUS_ACTIVE` |

## 2. Regras de Conformidade Arquitetural

### Hexagonal (Ports & Adapters)

```
✅ VÁLIDO:
  app/
    domain/
      entities.py         # Dataclasses puras, sem dependências
      value_objects.py    # Validação de negócio
    ports/
      repositories.py     # ABC para persistência
      services.py         # ABC para integração externa
    application/
      use_cases/
        create_user.py    # Lógica de negócio (injeta Ports)
    adapters/
      primary/
        http/
          deps.py         # Wiring do DI (FastAPI Depends)
          routes.py       # Endpoints thin (validação já está no domain)
      secondary/
        postgres/
          user_repository.py  # Implementa Port de repositório

❌ INVÁLIDO:
  - Lógica de negócio em rotas (fat controllers)
  - Dependências SQL diretas em use cases
  - Port sem implementação em adapter
  - Imports circulares (domain ← application ← adapters)
```

### Ordem de Imports (Python)
```python
# 1. Standard library
import asyncio
from typing import Optional

# 2. Third-party
from fastapi import FastAPI
import sqlalchemy

# 3. Local domain (no Relative)
from app.domain.entities import User
from app.ports.repositories import UserRepository

# 4. Local adapters
from app.adapters.secondary.postgres import PostgresUserRepository
```

## 3. Validação e Erros

### Exceções Customizadas (Python)
```python
# Padrão: <Entity><Error>
class UserNotFound(Exception):
    """Levantada quando user_id não existe em DB"""
    
class PermissionDenied(Exception):
    """Levantada quando usuário não tem acesso ao recurso"""

class ConversationLimitReached(Exception):
    """Levantada quando atingiu cota de conversas"""
```

### Status HTTP → Exceção
| Exceção | Status HTTP | Code de Erro |
|---------|------------|--------------|
| `UserNotFound` | 404 | `user_not_found` |
| `PermissionDenied` | 403 | `permission_denied` |
| `ConversationLimitReached` | 422 | `conversation_limit_reached` |
| `ValidationError` (Pydantic) | 400 | `validation_error` |
| Qualquer outra | 500 | `internal_server_error` |

## 4. Estrutura de Respostas de Erro

### Python/FastAPI
```python
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    code: str           # machine-readable
    message: str        # human-readable
    field: str | None   # para validation errors

class ErrorResponse(BaseModel):
    error: ErrorDetail

# Retorno:
# {"error": {"code": "user_not_found", "message": "Usuário não encontrado", "field": null}}
```

### Prefixos de Código de Erro por Domínio
| Prefixo | Domínio | Exemplos |
|---------|---------|----------|
| `auth_*` | Autenticação/Autorização | `auth_token_expired`, `auth_permission_denied` |
| `user_*` | Entidade User | `user_not_found`, `user_already_exists` |
| `conversation_*` | Entidade Conversation | `conversation_not_found`, `conversation_archived` |
| `environment_*` | Repo Environments (global) | `environment_not_found`, `environment_in_use` |
| `skill_*` | Skills/Agents | `skill_not_found`, `skill_timeout` |
| `validation_*` | Validação de Input | `validation_field_required`, `validation_invalid_email` |
| `agent_*` | Agent Runtime | `agent_unavailable`, `agent_timeout` |

## 5. Padrões de Teste

### Estrutura de Testes
```
services/
  api/
    tests/
      unit/
        domain/          # Testes de entities, value objects
        application/     # Testes de use cases (com mocks de ports)
        adapters/        # Testes de repositories, HTTP routes
      integration/       # Testes com DB real (fixtures)
      conftest.py        # Fixtures compartilhadas
```

### Naming Convention de Testes
```python
def test_<function>_<scenario>_<expected_outcome>():
    """
    test_fetch_user_by_id_not_found_raises_error
    test_create_conversation_valid_input_persists_to_db
    test_validate_email_invalid_format_returns_false
    """
```

## 6. Comentários e Documentação

### Quando Adicionar Comentários
✅ **Adicione:**
- Lógica complexa (ex: algoritmo não-óbvio)
- Trade-offs e por que essa solução foi escolhida
- Referências a issues (#123) ou ADRs
- Integrações externas e limites (timeout, rate limit)

❌ **Não adicione:**
- Comentários obvios (ex: `# incrementar x` antes de `x += 1`)
- Código comentado (use git blame se precisar ver histórico)
- Comentários desatualizados

### Docstrings em Python
```python
def fetch_user_by_id(user_id: str) -> User:
    """Busca um usuário por ID na base de dados.
    
    Args:
        user_id: UUID do usuário
        
    Returns:
        User object
        
    Raises:
        UserNotFound: Se user_id não existir
        
    Note:
        Esta chamada é N+1 com outras queries de perfil.
        Usar fetch_user_with_profile() em contextos de lista.
    """
```

## 7. Configuração e Environment

### Variáveis de Ambiente
```bash
# Padrão: <SERVICE>_<COMPONENT>_<SETTING>
SERVICE_COMPONENT_SETTING=value

# Exemplos (CappyCloud):
CAPPYCLOUD_API_DEBUG=false
CAPPYCLOUD_AGENT_GRPC_PORT=50051
CAPPYCLOUD_AGENT_TIMEOUT_SEC=30
CAPPYCLOUD_DATABASE_URL=postgresql://...

# Não fazer:
# DEBUG=true (muito genérico)
# api_debug=false (use screaming snake case)
```

### Valores Padrão
```python
# Em schemas, portas, use cases — sempre explícito
DEFAULT_PAGE_SIZE = 20
DEFAULT_TIMEOUT_SEC = 30
MAX_MESSAGE_LENGTH = 2000
```

## 8. Controle de Qualidade

### Linhas por Arquivo
| Tipo | Máximo |
|------|--------|
| Classe de domínio | 100 |
| Use case | 300 |
| Adapter secundário | 400 |
| Route/Handler | 200 |
| Função utilitária | 50 |

Arquivos maiores devem ser refatorados em módulos menores.

### Complexidade Ciclomática
- Máximo 10 por função
- Se atingir, considere extrair condicionais para Value Objects ou métodos privados

### Code Review Checklist
- [ ] Segue naming conventions desta skill
- [ ] Hexagonal: domain puro, ports definidas, adapters isolados
- [ ] Tratamento de erros com exceções customizadas
- [ ] Testes unitários para lógica de negócio
- [ ] Sem comentários obsoletos ou óbvios
- [ ] Arquivo < máximo de linhas recomendado
- [ ] Tipos anotados (Python: type hints; TypeScript: types)

---

**Disponível em**: `sandbox/skills/global/`  
**Escopo**: Global — todos os repositórios e agentes  
**Última atualização**: maio 2026
