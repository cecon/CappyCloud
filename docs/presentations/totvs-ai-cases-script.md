# Cappy — Roteiro Falado · Fórum TOTVS de Cases de IA

> Texto completo de palco. 15 minutos. ~1875 palavras.
> Marcação de tempo em [colchetes]. Pausa = `//`. Ênfase = **negrito**.

---

## Slide 1 — Capa · [0:00 → 0:30]

> "Boa tarde a todos. // Obrigado pelo espaço aqui no fórum.
>
> Nos próximos quinze minutos eu quero apresentar a **Cappy**. // Cappy é uma
> plataforma de agentes de IA com sandbox isolado, // e ela conversa
> diretamente com as iniciativas que a TOTVS já mostrou nos slides anteriores —
> o Chatbot Protheus, o Assistente Release, o Produtividade Implantação.
>
> A proposta dessa apresentação não é mostrar mais uma iniciativa concorrente. //
> A proposta é mostrar uma **camada de plataforma** que pode sustentar todas elas."

---

## Slide 2 — O problema · [0:30 → 2:00]

> "Quando a gente olha pro slide das iniciativas que foi apresentado mais cedo, //
> a gente vê três agentes diferentes resolvendo problemas diferentes. // Tudo
> ótimo. // O Chatbot Protheus responde sobre documentação. // O Assistente
> Release responde sobre novidades da versão. // O Produtividade Implantação
> ajuda a criar MITs.
>
> Mas se a gente olhar embaixo do capô, // os **três** estão resolvendo os
> mesmos cinco problemas de infraestrutura:
>
> **Primeiro:** isolamento. // Como garantir que a franquia A não enxerga o
> dado da franquia B? // Isso é Docker, é rede, é limite de processo.
>
> **Segundo:** sessão. // O usuário fechou o browser, abriu de novo — // a
> conversa continua de onde parou? // Isso é estado em Redis, em PostgreSQL.
>
> **Terceiro:** streaming. // O agente está pensando, // a resposta tem que
> aparecer letra por letra. // Isso é gRPC bidirecional, // é controle de
> backpressure.
>
> **Quarto:** modelo. // Hoje é Claude, // amanhã pode ser GPT, // depois de
> amanhã pode ser um Llama on-premise. // Como trocar sem reescrever o agente?
>
> **Quinto:** humano no meio. // O agente vai fazer algo sensível — // como
> pausar e esperar a aprovação?
>
> O ponto é: // cada iniciativa hoje está reinventando esses cinco itens // do
> zero. // É aí que a Cappy entra."

---

## Slide 3 — Cappy em uma frase · [2:00 → 3:00]

> "Cappy é uma frase: // **a infraestrutura que sustenta agentes**. // Ela
> não é mais um chatbot, // ela é o que estaria embaixo de um chatbot se ele
> rodasse sobre nossa plataforma.
>
> Em termos concretos: // o usuário acessa pelo navegador, // a requisição
> chega numa API FastAPI, // e a API sobe um **container Docker dedicado**
> para aquele par de usuário e conversa. // Dentro desse container roda o
> agente — // a gente usa o openclaude — // se comunicando por gRPC. // E o
> agente fala com o modelo via OpenRouter, // que é um gateway que abstrai
> qual LLM está por trás.
>
> Os pontos fortes ficam claros: // **um container por conversa**, // **um
> git worktree por conversa** — // ou seja, o agente tem um workspace
> de verdade, não só prompt — // **sessão persistida** em Redis e PostgreSQL —
> e // **retomada controlada** quando precisa de humano no meio.
>
> É isso. // O resto da apresentação é mostrar essas capacidades em detalhe."

---

## Slide 4 — Capacidade 1: Isolamento real · [3:00 → 4:30]

> "Primeira capacidade — // e essa eu quero que os executivos prestem atenção. //
>
> A maioria dos chatbots hoje é isolamento **lógico**. // Todo mundo no mesmo
> processo, // contextos separados por chave de sessão. // Funciona — // até
> alguém achar um bug que vaza contexto entre sessões. // E aí você tem um
> incidente de LGPD na mão.
>
> A Cappy faz isolamento **físico**. // Não é o software que separa franquia
> A de franquia B — // é o **kernel do Linux**. // São containers diferentes,
> filesystems diferentes, processos diferentes, redes diferentes.
>
> Pra ficar concreto: // a franquia A está conversando com o agente. // O
> agente tá rodando no container A. // A franquia B abre uma conversa
> paralela. // Container B, totalmente novo. // Não tem como — // por bug,
> por race condition, por qualquer coisa — // o agente da B enxergar dado da A.
>
> Pro arquiteto: // o código que faz isso está no `EnvironmentManager`. // Ele
> mantém um mapa de containers por par usuário-conversa, // cria git worktree
> isolado, // e destrói tudo depois do timeout de inatividade.
>
> Pro executivo: // esse é o argumento que fecha conversa com jurídico. //
> Quando aparecer cliente perguntando como você garante separação de dados, //
> a resposta é container, não promessa."

---

## Slide 5 — Capacidade 2: Sessão retomável e Human-in-the-Loop · [4:30 → 6:00]

> "Segunda capacidade. // Essa é talvez a mais subestimada do mercado.
>
> Imaginem o cenário: // o agente está ajudando o consultor a criar um MIT. //
> Em algum ponto, // ele vai fazer uma operação **sensível** — // por
> exemplo, escrever num cadastro de produção, // ou rodar um script que altera
> dados.
>
> A pergunta é: // o agente faz sozinho? // Ou pede confirmação?
>
> Se faz sozinho, // você está confiando demais. // Se você bloqueia tudo
> que é sensível, // você na prática **não usa** IA. // O meio-termo é
> human-in-the-loop, // e quase nenhuma plataforma faz isso direito.
>
> Cappy faz nativamente. // O fluxo é: // o agente trabalha, // detecta uma
> ação que precisa de aprovação, // e emite um evento que a gente chama de
> `ActionRequired`. // Nesse momento o stream **pausa**. // O frontend mostra
> 'aprovar / negar'. // O usuário decide. // E o `send_input` retoma o
> stream **exatamente** de onde parou.
>
> E mais importante: // se o usuário fecha o browser nesse meio, // a sessão
> sobrevive. // Reabre amanhã, // o agente está lá, // esperando.
>
> Isso vem de graça. // Não é integração com nenhuma fila externa. // Está
> no `GrpcSession` do nosso agente.
>
> Pro executivo, traduzindo: // toda iniciativa de IA que envolve aprovação
> humana — // compliance, // financeiro, // qualquer coisa regulada — // já
> tem a peça mais difícil resolvida."

---

## Slide 6 — Capacidade 3: Gateway-agnóstico e Hexagonal · [6:00 → 7:30]

> "Terceira capacidade. // Vendor lock-in zero.
>
> A escolha do modelo de linguagem hoje é uma das decisões mais voláteis de
> qualquer projeto de IA. // Anthropic sobe preço, // OpenAI lança modelo
> melhor, // sai um Llama 70B que cabe on-premise. // Toda semana muda.
>
> Na Cappy, // trocar o modelo é mudar **uma variável de ambiente**. //
> `OPENROUTER_MODEL` é Claude hoje, // é GPT-4 amanhã, // é Llama depois. //
> Zero código alterado.
>
> Isso é o nível raso. // O nível mais profundo é a arquitetura hexagonal. //
> A gente seguiu **ports and adapters** desde o começo — // tem ADR
> documentando a decisão.
>
> Na prática isso significa: // o banco de dados é um adapter — // hoje
> SQLAlchemy com Postgres, // amanhã pode ser outro. // A autenticação é um
> adapter — // hoje JWT, // amanhã SAML ou OIDC para integrar com o SSO da
> TOTVS. // O sandbox é um adapter — // hoje Docker local, // amanhã
> Kubernetes multi-região.
>
> Pro arquiteto: // quem quiser olhar, // está em
> `docs/decisions/adr-001-hexagonal-architecture.md`. // Os ports são ABCs
> puras em Python, // os adapters implementam, // os use cases não conhecem
> infraestrutura.
>
> Pro executivo: // isso é o que protege o investimento. // A plataforma
> não amarra a TOTVS a fornecedor nenhum. // Nem a Anthropic, // nem a OpenAI,
> // nem ao Docker."

---

## Slide 7 — Caso A: Assistente Release sobre Cappy · [7:30 → 9:00]

> "Agora vou pegar dois casos concretos que vocês apresentaram e mostrar
> como ficariam sobre a Cappy. // O primeiro é o **Assistente de Release**.
>
> Lembrando o que ele faz hoje: // agente treinado em documentação da release, //
> responde perguntas sobre as novidades da versão. // No exemplo que apareceu,
> // era a 12.1.2 do Protheus, // com módulos de Saúde, Jurídico, Transporte
> de Passageiros.
>
> Sobre a Cappy, // esse mesmo caso ganha quatro coisas:
>
> **Um:** // ao invés do agente ler só a documentação, // ele tem acesso ao
> **repositório real** da release. // Pergunta sobre uma feature? // O agente
> abre o commit que introduziu, // mostra o diff, // mostra o teste.
>
> **Dois:** // multi-tenant nativo. // Cada franquia, // cada cliente-chave,
> // entra num container próprio. // Sem mistura de contexto.
>
> **Três:** // atualizar a base de conhecimento é trocar o branch do git
> worktree. // Não tem rebuild de índice, // não tem reembedar vetor. // É
> `git checkout`.
>
> **Quatro:** // múltiplas releases em paralelo. // 12.1.2, 12.1.3, 12.1.4 —
> // cada uma com seu workspace. // O mesmo agente atende todas.
>
> Pra entender a diferença: // o assistente atual é **texto sobre texto**. //
> Sobre a Cappy ele é **texto sobre código**. // E código é a fonte da
> verdade, // documentação fica desatualizada."

---

## Slide 8 — Caso B: Produtividade de Implantação sobre Cappy · [9:00 → 10:30]

> "Segundo caso. // **Produtividade Implantação** — // chatbots para auxiliar
> na criação de MITs e aceleradores.
>
> Aqui o ganho de plataforma é ainda mais claro, // porque a iniciativa atual
> é fundamentalmente **sugestiva**. // O chatbot sugere, // o consultor copia
> e cola, // executa fora do chatbot. // Trabalho ainda manual.
>
> Sobre a Cappy isso vira **executável**.
>
> O agente está dentro de um container com git, // com node, // com as
> ferramentas reais de desenvolvimento. // Quando o consultor pede um MIT, //
> o agente:
>
> Cria os arquivos. // De verdade. // No workspace dele. // Roda o scaffolding.
> // Valida sintaxe. // Roda os testes. // E **só então** mostra o resultado
> pro consultor.
>
> Se errou — // descarta o container. // Não suja ambiente nenhum. // Não tem
> 'volte ao backup'. // É efêmero.
>
> Se acertou — // o consultor revisa, // aprova com aquele mecanismo
> `ActionRequired` que eu mostrei, // e o agente abre o pull request.
>
> A diferença prática: // hoje o ganho de produtividade é da ordem de
> sugestão. // Sobre a Cappy é da ordem de **execução**. // É outra
> categoria de ganho."

---

## Slide 9 — Status atual · [10:30 → 11:30]

> "Antes de fechar, // quero ser muito direto sobre o **estado** da Cappy
> hoje. // Porque slide é fácil, // código é difícil.
>
> O que está pronto, // rodando, // testado:
>
> Backend FastAPI com arquitetura hexagonal completa, // // testes unitários,
> // testes de contrato dos adapters, // testes de integração HTTP via httpx.
>
> Agente openclaude empacotado numa imagem de sandbox versionada.
>
> Frontend React com Vite e Mantine. // Login, // conversas, // streaming em
> tempo real, // tudo funcional.
>
> Orquestração inteira via Docker Compose. // Um comando sobe a stack —
> Postgres, Redis, API, web, sandbox.
>
> Persistência dupla: // Redis pras sessões quentes com TTL, // PostgreSQL pro
> histórico permanente.
>
> Contrato gRPC versionado no protobuf.
>
> Resumindo: // **isso não é PowerPoint-ware**. // É código rodando hoje.
> Depois da sessão, // quem quiser, // eu rodo aqui no notebook e mostro uma
> conversa real."

---

## Slide 10 — Próximo passo · [11:30 → 13:00]

> "Encerrando.
>
> A proposta concreta que estamos trazendo pro fórum é:
>
> **Um piloto.** // Trinta dias. // Uma das iniciativas TOTVS rodando sobre
> Cappy. // A sugestão da gente é o Assistente Release, // porque o escopo
> é bem definido e o valor aparece rápido.
>
> Em paralelo a esse piloto, // a gente roda um **comparativo
> lado-a-lado** com a implementação atual. // Métricas concretas: //
> isolamento entre clientes, // custo por sessão, // tempo pra entregar uma
> feature nova no agente.
>
> No fim dos trinta dias, // a TOTVS tem uma **decisão informada** sobre
> usar a Cappy como base das próximas iniciativas, // ou seguir com o modelo
> atual de cada equipe construindo do zero.
>
> O que precisamos pro piloto: // acesso à documentação de uma release pra
> alimentar o agente, // um arquiteto da TOTVS como contraparte técnica
> pra integração, // e os trinta dias.
>
> É isso. // Obrigado a todos. // Tô aberto a perguntas." // [13:00]

---

## Buffer e Q&A · [13:00 → 15:00]

Dois minutos de respiro pra:

- Transições mais lentas se a plateia estiver fria
- Pergunta do moderador
- Demo curta se o ambiente estiver pronto

### Respostas curtas pras perguntas mais prováveis:

**"Por que não usar Dify, LangChain, ou serviço X?"**

> "Camadas diferentes. // Dify e LangChain são frameworks de orquestração
> de prompt. // Cappy é runtime de agente com sandbox isolado. // Aliás, //
> dá pra rodar LangChain **dentro** do nosso sandbox. // Eles se somam,
> não se substituem."

**"E custo de container por usuário?"**

> "TTL configurável, // padrão de 30 minutos. // Container morre depois da
> inatividade. // Em produção, // com pool e reaproveitamento, // o overhead
> de container é marginal frente ao custo do LLM em si — // que é onde está
> 90% do gasto."

**"Como integra com o SSO da TOTVS?"**

> "Auth é um adapter. // Hoje JWT, // amanhã SAML ou OIDC. // Sem mexer no
> resto do código. // É exatamente o caso de uso da arquitetura hexagonal."

**"E observabilidade?"**

> "Logs estruturados por container, // sessão rastreável em PostgreSQL, //
> métricas de gRPC. // Pronto pra plugar em Datadog, // Grafana, // o que a
> TOTVS já usa."

**"Funciona multi-região?"**

> "O `EnvironmentManager` é um adapter. // Hoje é Docker local, // amanhã
> pode ser Kubernetes em região A, B, C. // Mesma interface, // outro adapter."

**"E se o openclaude mudar o protocolo?"**

> "Por isso o protobuf é versionado em `proto/openclaude.proto`. // A gente
> consome um contrato, // não um binário. // Versão nova do openclaude — //
> regera os stubs, // adapta se mudou.

---

## Notas de execução

- **Velocidade:** ~125 palavras/min é o ritmo confortável de palco. Esse roteiro
  totaliza ~1875 palavras = **15 minutos** com folga pra respiros marcados (`//`).
- **Slides como apoio:** não leia o slide. Os bullets do `totvs-ai-cases.md`
  são reforço visual; o texto falado vem daqui.
- **Demo opcional:** se sobrar tempo no buffer, abrir `http://localhost:38081`
  e mostrar uma conversa real fecha com chave de ouro.
- **Tom:** alterne deliberadamente entre "pro executivo" e "pro arquiteto" —
  está marcado no roteiro. Isso mantém as duas audiências engajadas.
