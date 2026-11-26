# 018 — Mesmo modelo em dois providers

## Pedido

Alef (admin dos workspaces PROTHEUS), 2026-11-26: usar o "Claude Opus 5.5
(Lynn)" pelo proxy do Lynn. O modelo `claude-opus-5-5` já existia no provider do
Azure. A Cappy achava o provider pelo nome do modelo (`model_id`), então a
conversa ia para o Azure. Por isso a linha do Lynn ficou desativada.

## Regras

- O chat escolhe a linha do catálogo (`ai_models.id`), não só o nome. O seletor
  guarda o id da linha e manda esse id em `model_id` ao criar a conversa e ao
  enviar mensagem.
- A API aceita em `model_id` o id da linha ou o nome do modelo:
  - id: vale só aquela linha (ativa, de texto, com provider ativo).
  - nome: vale a primeira linha com esse nome que o usuário pode usar, com a
    default de texto primeiro. É o comportamento de antes, para scripts e
    preferências salvas antes da mudança.
- `conversations.ai_model_id` grava a linha pedida. O pipeline manda essa linha
  ao agente (`ai_model_id`), e o agente usa o provider dela.
- O agente só usa a linha se ela tiver o mesmo `model_id` do modelo que vai
  rodar. Sem linha, ou se ela não bater (por exemplo, quando o fallback trocou o
  modelo), vale a primeira linha ativa com esse nome, como antes.
- O nome do modelo (`model_used`) continua igual em custo, relatórios e
  timeline. O preço é o de lista do modelo, o mesmo nos dois providers.
- O catálogo já permitia o mesmo `model_id` em providers diferentes
  (unicidade só por provider). Não há migration.

## Implementação

- API:
  - `sqlalchemy_ai_model_access_policy.py`: aceita o id da linha; pelo nome,
    escolhe a primeira linha liberada para o usuário.
  - `conversation_create_helpers.resolve_ai_model_id` usa a mesma regra.
  - `SendMessage` resolve a linha a partir do pedido, não do nome já resolvido.
  - `build_pipeline_body` inclui `ai_model_id`.
- Agente: `cappycloud_pipeline` → `TaskDispatcher` → `launch_runner` →
  `resolve_model_provider_runtime_config(model_id, ai_model_id)`.
- Web:
  - `model-picker/modelKey.ts` (`findModel`): acha pelo id; um nome salvo antes
    da mudança cai na linha default, ou na primeira.
  - O seletor, as preferências e a troca de modelo por imagem usam o id.

## Testes

- `tests/unit/test_ai_provider_runtime_config.py`: o provider segue a linha
  escolhida e cai no nome quando ela não bate.
- `tests/unit/test_ai_model_access_choice.py`: o id da linha, o nome e o acesso
  por usuário.
- `tests/unit/use_cases/test_stream_helpers.py`: o corpo do pipeline leva
  `ai_model_id`.
- `web`: `ModelPicker.test.tsx` (mesmo modelo em dois providers) e
  `model-picker/modelKey.test.ts`.
