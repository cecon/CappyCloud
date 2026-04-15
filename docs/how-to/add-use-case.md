# Como criar um novo use case

Use cases são a camada onde **toda** a lógica de negócio do CappyCloud vive.
Eles não conhecem FastAPI, SQLAlchemy, Docker — só ports (ABCs).

---

## Onde ficam

```
services/api/app/application/use_cases/
  auth.py           ← RegisterUser, LoginUser, GetCurrentUser
  conversations.py  ← CreateConversation, StreamMessage, ListMessages, …
```

Se o novo use case pertence a um contexto existente, adicione no arquivo
correspondente. Se for um contexto novo, crie um arquivo novo.

---

## Estrutura padrão

```python
class NomeDoUseCase:
    """Descrição de uma linha do que o use case faz."""

    def __init__(self, dep1: Port1, dep2: Port2) -> None:
        self._dep1 = dep1
        self._dep2 = dep2

    async def execute(self, param1: str, param2: uuid.UUID) -> Entidade:
        """Descrição do contrato.

        Raises:
            ValueError: se a entrada for inválida.
            LookupError: se o recurso não existir.
            PermissionError: se o acesso for negado.
        """
        # 1. Validar inputs (delegar para value_objects.py se for regra de domínio)
        # 2. Buscar estado necessário via ports
        # 3. Aplicar regras de negócio
        # 4. Persistir / disparar efeitos via ports
        # 5. Retornar entidade de domínio
```

---

## Regras obrigatórias

1. **Só ports como dependências.** Nunca injetar `AsyncSession`, `docker.DockerClient`
   ou qualquer implementação concreta.

2. **Input e output são tipos de domínio.** Nunca retornar dicts soltos ou modelos
   Pydantic — retorne entidades definidas em `app/domain/entities.py`.

3. **Exceções semânticas.** Use as exceções padrão Python com significado claro:
   - `ValueError` — input inválido ou regra de negócio violada
   - `LookupError` — recurso não encontrado
   - `PermissionError` — acesso negado
   O router HTTP converte essas exceções nos status codes HTTP corretos.

4. **Máximo 300 linhas por arquivo.** Dividir por responsabilidade se exceder.

5. **Type annotations em tudo** — `mypy app/` deve passar com zero erros.

---

## Adicionando uma nova Port

Se o use case precisa de uma nova dependência (ex.: serviço de notificação):

1. Defina o ABC em `app/ports/`:

   ```python
   # app/ports/services.py
   class NotificationService(ABC):
       @abstractmethod
       async def notify(self, user_id: uuid.UUID, message: str) -> None: ...
   ```

2. Crie o adapter real em `app/adapters/secondary/`:

   ```python
   # app/adapters/secondary/email_notification.py
   class EmailNotificationService(NotificationService):
       async def notify(self, user_id: uuid.UUID, message: str) -> None:
           ...  # implementação real
   ```

3. Crie o fake em `tests/conftest.py`:

   ```python
   class FakeNotificationService(NotificationService):
       def __init__(self) -> None:
           self.sent: list[tuple[uuid.UUID, str]] = []

       async def notify(self, user_id: uuid.UUID, message: str) -> None:
           self.sent.append((user_id, message))
   ```

4. Adicione testes de contrato em `tests/adapter/` verificando que ambas as
   implementações satisfazem o mesmo comportamento.

---

## Testes obrigatórios

Todo use case deve ter testes unitários em `tests/unit/`. Use **apenas fakes**
em memória — sem DB, sem rede, sem Docker.

```python
# tests/unit/test_meu_use_case.py
import pytest
from app.application.use_cases.conversations import MeuUseCase

@pytest.mark.asyncio
async def test_caso_feliz(fake_repo, fake_service):
    uc = MeuUseCase(repo=fake_repo, service=fake_service)
    resultado = await uc.execute("input válido")
    assert resultado.campo == "valor esperado"

@pytest.mark.asyncio
async def test_input_invalido_levanta_value_error(fake_repo):
    uc = MeuUseCase(repo=fake_repo)
    with pytest.raises(ValueError, match="mensagem esperada"):
        await uc.execute("")
```

---

## Wiring no router

Depois de criar o use case, registre o factory em `deps.py`:

```python
def get_meu_use_case(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MeuUseCase:
    return MeuUseCase(repo=SqlAlchemyMeuRepo(db))
```

Ver `docs/how-to/add-endpoint.md` para o passo a passo completo do router.
