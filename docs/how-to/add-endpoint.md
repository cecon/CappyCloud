# Como adicionar um novo endpoint HTTP

Passo a passo obrigatório para adicionar endpoints FastAPI respeitando a
arquitetura hexagonal do CappyCloud.

---

## Pré-requisitos

- Entender o fluxo: router → use case → port → adapter
- Ler `docs/ARCHITECTURE.md` e `docs/AGENT_RULES.md` antes de começar

---

## Passo 1 — Definir schemas Pydantic

Arquivo: `services/api/app/schemas.py`

Crie os modelos de request/response. Validators devem **delegar** para funções
em `domain/value_objects.py` — nunca duplicar a lógica de validação.

```python
class MeuRecursoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=256)

class MeuRecursoOut(BaseModel):
    id: uuid.UUID
    nome: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

---

## Passo 2 — Criar o use case

Arquivo: `services/api/app/application/use_cases/<contexto>.py`

Toda lógica de negócio vive aqui. O use case **só conhece ports (ABCs)** —
nunca importa SQLAlchemy, FastAPI ou Docker diretamente.

```python
class CriarMeuRecurso:
    def __init__(self, repo: MeuRecursoRepository) -> None:
        self._repo = repo

    async def execute(self, nome: str) -> MeuRecurso:
        # validação de negócio aqui (se houver)
        recurso = MeuRecurso(id=uuid.uuid4(), nome=nome)
        return await self._repo.save(recurso)
```

Se o use case precisar de uma dependência nova, vá ao Passo 2a.

### Passo 2a — Criar a Port (se necessária)

Arquivo: `services/api/app/ports/repositories.py` (ou `services.py`)

```python
class MeuRecursoRepository(ABC):
    @abstractmethod
    async def save(self, recurso: MeuRecurso) -> MeuRecurso: ...

    @abstractmethod
    async def get(self, recurso_id: uuid.UUID) -> MeuRecurso | None: ...
```

Depois de criar a port, crie também:
- Adapter real em `app/adapters/secondary/` (SQLAlchemy)
- Fake em memória em `tests/conftest.py` (para testes unitários)

---

## Passo 3 — Criar a entidade de domínio (se necessária)

Arquivo: `services/api/app/domain/entities.py`

```python
@dataclass
class MeuRecurso:
    id: uuid.UUID
    nome: str
    created_at: datetime = field(default_factory=_utcnow)
```

Zero dependências externas — apenas stdlib.

---

## Passo 4 — Adicionar o router HTTP

Arquivo: `services/api/app/adapters/primary/http/<contexto>.py`

O router é **thin**: só parseia o request, chama o use case, retorna o response.
Proibido: lógica de negócio, queries SQL, acesso direto a repos.

```python
router = APIRouter(prefix="/meus-recursos", tags=["meus-recursos"])

@router.post("", response_model=MeuRecursoOut, status_code=status.HTTP_201_CREATED)
async def criar_recurso(
    body: MeuRecursoCreate,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[CriarMeuRecurso, Depends(get_criar_recurso_uc)],
) -> MeuRecursoOut:
    recurso = await uc.execute(body.nome)
    return MeuRecursoOut.model_validate(recurso)
```

Registar o router em `services/api/app/main.py`:

```python
from app.adapters.primary.http import meu_recurso
app.include_router(meu_recurso.router)
```

---

## Passo 5 — Wiring de dependências

Arquivo: `services/api/app/adapters/primary/http/deps.py`

Adicione o factory do use case:

```python
def get_criar_recurso_uc(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CriarMeuRecurso:
    return CriarMeuRecurso(repo=SqlAlchemyMeuRecursoRepository(db))
```

---

## Passo 6 — Testes

### Unitário (sem DB, sem HTTP)

Arquivo: `services/api/tests/unit/test_meu_recurso.py`

```python
async def test_criar_recurso_persiste():
    repo = FakeMeuRecursoRepository()
    uc = CriarMeuRecurso(repo=repo)
    recurso = await uc.execute("meu nome")
    assert recurso.nome == "meu nome"
    assert len(repo.items) == 1
```

### Integração (HTTP + DI overrides)

Arquivo: `services/api/tests/integration/test_meu_recurso_http.py`

```python
async def test_post_cria_recurso(client: AsyncClient):
    r = await client.post("/meus-recursos", json={"nome": "teste"})
    assert r.status_code == 201
    assert r.json()["nome"] == "teste"
```

---

## Passo 7 — Validar

```bash
cd services/api
ruff check .
mypy app/
pytest
```

Todos devem passar com zero erros antes de abrir PR.
