# MedPulse

Painel de triagem hospitalar para TV: um mural de monitoramento contínuo que mostra o fluxo de atendimentos em tempo real — sem rolagem, sem interação operacional e sem nenhum dado de paciente.

O projeto parte de um wireframe e entrega uma interface de nível comercial sobre uma API Flask, um banco relacional e um WebSocket, com um **ambiente de demonstração autônomo** (hospital sintético "UBA Londres") que gera movimento contínuo e verossímil para apresentação pública e portfólio.

![Painel MedPulse em Full HD](docs/screenshots/painel-desktop.png)

---

## Funcionalidades

**O que o painel mostra**
- Seis indicadores: aguardando triagem, em atendimento, atendidos no período, espera média (com o tempo do atendimento mais antigo na fila), tempo em atendimento e projeção da fila — cada card com sparkline da série recente.
- Matriz **fila por prioridade** × etapa (fila · em atendimento · concluídos · espera média), na ordem assistencial.
- **Fluxo de atendimento**: série horária de chegadas × conclusões × fila, no fuso da operação.
- **Tempo de espera**: distribuição agregada da fila atual em faixas (até 15 min · 15–30 · 30–60 · 1–2 h · 2–4 h · acima de 4 h), separando quem aguarda de quem já está em atendimento.
- **Atendidos por prioridade** com percentuais, e **alertas de triagem** cujas regras são avaliadas no servidor.
- Card "Por unidade monitorada", que evidencia a separação entre hospitais reais e o ambiente demo.

**Feito para uma tela na parede**
- Nada rola: em 1920×1080 (e em qualquer resolução maior) toda a informação cabe no viewport, sem barra de rolagem na página nem dentro dos cartões.
- Tipografia escalonada pela largura da tela (`clamp()` na unidade `rem`), números tabulares e rótulos legíveis a distância.
- Quatro controles apenas: seleção de hospitais, relógio, tema claro/escuro e tela cheia. O estado de conexão é um selo, não um botão.
- Botão de atualização manual não existe: os números chegam sozinhos pelo WebSocket.
- Modo parede (Fullscreen API) preservando fundo, tema e distribuição dos componentes.

![Tela cheia](docs/screenshots/painel-tela-cheia.png)

**Privacidade por construção**
- O painel é agregado: nomes, protocolos/prontuários, documentos, setores e qualquer campo clínico **não chegam ao navegador**. A projeção `CAMPOS_PAINEL` em `services/realtime.py` define o único conjunto de campos que atravessa a borda (REST, snapshot e eventos), de modo que expor um dado pessoal exigiria alterar o backend — não basta ocultar com CSS.
- O estado do frontend (`static/js/state.js`) não guarda linhas de paciente: armazena apenas indicadores, vocabulário e contadores de eventos.

**Multi-tenant e seleção**
- Escopo por *local* via token na URL (`/{token}`): cada instalação enxerga apenas seus hospitais.
- Multiselect de um ou mais hospitais com atalhos "Todos / Somente demo"; hospitais de demonstração são marcados visualmente. A seleção persiste no navegador por local e nunca fica vazia.
- Cada agregado devolvido pela API carrega o escopo com que foi calculado (`resumo.hospitais`), e o store só aceita payload cujo escopo bate com a seleção atual — respostas que chegam fora de ordem durante uma troca rápida de seleção são descartadas em vez de misturar unidades.
- O painel suspenso vive no `<body>` (ou no elemento em tela cheia) com posição fixa: nenhum contexto de empilhamento do cabeçalho o esconde — comportamento idêntico em Chromium e Firefox.

**Tempo real e resiliência**
- Socket.IO por sala (`hospital:<id>`); o navegador assina somente os hospitais selecionados.
- Snapshot (`painel:snapshot`) no connect e no resubscribe → sincronização inicial e reconciliação após reconexão, sem duplicar registros nem aplicar eventos fora de ordem.
- Selo de conexão com dois estados e nenhuma zona cinzenta: **Online** somente enquanto o WebSocket está estabelecido; **Offline** quando ele ainda não conectou, caiu ou foi perdido — a página carregada não conta como conexão.
- Reconexão automática com backoff; se o socket não voltar, o painel cai para consulta REST periódica (modo reserva) e retorna ao socket quando ele recupera.
- Atualização apenas dos componentes inscritos no canal que mudou.

**Relógio do servidor**
- A referência temporal é o fuso da operação (`TIMEZONE`, IANA), não o da TV: `/api/config` entrega `fuso_horario`, `agora_utc` e `agora_local`, e o navegador sincroniza apenas o deslocamento em relação ao servidor.
- O deslocamento é recalculado com os agregados que já passam pelo socket (`resumo.gerado_em`), sem requisição extra de horário; entre sincronizações o relógio avança localmente e a formatação usa `Intl.DateTimeFormat({ timeZone })`.

**Ingestão**
- `POST /api/webhook/atendimentos` idempotente por `protocolo`, guarda de ordem por `atualizado_em`, updates parciais (status ou prioridade) e `409` para transição inválida.

**Showcase**
- Gerador sintético contínuo, isolado e configurável — detalhado abaixo.

**Paleta de prioridade (escala oficial)**

| Prioridade | Tema escuro | Tema claro |
|---|---|---|
| Alta | `#f2384f` (vermelho) | `#d1132f` (vermelho) |
| Intermediária | `#f7c531` (amarelo) | `#eab308` (amarelo) |
| Baixa | `#1f9d55` (verde) | `#16803d` (verde) |
| Não urgente | `#3b74f0` (azul) | `#1257c9` (azul) |
| Sem triagem | `#f3f8fb` (**branco**) | `#101317` (**preto**) |

A escala é definida por tokens (`--p-alta`, `--p-intermediaria`, `--p-baixa`, `--p-nao_urgente`, `--p-sem_triagem`, com o par `--p-*-fg` para o texto sobre o preenchimento) e é a mesma em matriz, cartões, contadores, legendas e gráficos. Os tons do tema claro são escurecidos para manter contraste sobre fundo branco sem trocar a leitura da cor. As séries do gráfico de fluxo usam tokens próprios (`--serie-chegada`, `--serie-conclusao`, `--serie-fila`) justamente para que nenhuma cor de gráfico possa ser lida como prioridade de triagem, e o selo de conexão é texto + pílula, não um ponto colorido.

![Tema claro](docs/screenshots/painel-tema-claro.png)


---

## Arquitetura

```
┌─────────────────┐   REST (GET /api/…)    ┌──────────────────────────┐
│  Navegador      │ ─────────────────────► │  Flask                   │
│  ES modules +   │                        │  routes/ → services/     │
│  Chart.js +     │ ◄───────────────────── │  → models (SQLAlchemy)   │
│  socket.io      │   WebSocket (sala      │                          │
│  store pub/sub  │   hospital:<id>)       └────┬────────────┬────────┘
└─────────────────┘                             │            │
                                        ┌───────▼──────┐  ┌───▼─────────────┐
        Sistema externo ◄── webhook ───►│  Banco       │  │ showcase.py     │
        POST /api/webhook/atendimentos  │  Postgres /  │  │ thread própria, │
                                        │  SQLite      │  │ só demo = True  │
                                        └──────────────┘  └─────────────────┘
```

**Fluxo de um evento**

1. O sistema de origem publica no webhook (ou o gerador sintético cria o atendimento direto no banco pela camada de serviços).
2. `services/atendimentos.py` valida a transição contra a máquina de estados do model, grava e marca o hospital como "sujo".
3. `services/metricas.py` coalesce os recálculos: uma thread de fundo agrupa hospitais sujos por seleção distinta e recalcula indicadores, filas e distribuição de espera **uma vez** por janela (~0,6 s). A API é a única fonte de verdade dos agregados.
4. `services/realtime.py` projeta o atendimento em `CAMPOS_PAINEL` e emite o evento na sala do hospital (`atendimento:novo`, `atendimento:atualizado`, `resumo:atualizado`).
5. O navegador recebe, aplica no store e atualiza somente os componentes inscritos naquele canal.

**Decisões relevantes**
- **Sem segunda fonte de verdade no frontend.** O vocabulário de estados vem de `/api/config` (STATUS, TRANSICOES, ESTADOS_FINAIS, PRIORIDADES definidos em `models/atendimentos.py`); o navegador não duplica regras de negócio, não agrega filas e não calcula durações a partir de campos locais — só formata o que a API entrega.
- **Privacidade na borda, não na camada de apresentação.** `CAMPOS_PAINEL` (`services/realtime.py`) é a lista branca de campos que um atendimento pode atravessar para o navegador: `id`, `hospital_id`, `status`, `prioridade`, `hora_inicio`, `hora_final`, `atualizado_em`. Nome, protocolo, documento e setor ficam no servidor, então o painel de TV *não tem* dados pessoais a ocultar.
- **Agregação no servidor.** Escalabilidade e coerência: KPI, matriz de prioridade, série horária e faixas de espera saem prontos da API — a mesma resposta REST e o mesmo snapshot usam o mesmo código.
- **Relógio com uma única referência.** `utils/tz.py` + `TIMEZONE` definem `FUSO_HORARIO`; a API carimba `gerado_em`/`agora_utc` e o navegador mantém só o deslocamento. A hora da TV é a hora do servidor.
- **Máquina de estados explícita.** Transições inválidas são rejeitadas na borda (`409`), o que vale igualmente para o webhook e para o gerador.
- **Identidade visual própria.** CSS com design tokens derivados da logo (verde/azul), sem framework de UI; Chart.js e socket.io vendorizados em `static/vendor/` — nenhuma dependência de CDN.
- **Migrações estritamente aditivas** (Flask-Migrate/Alembic), seguras contra um banco compartilhado.

---

## Tecnologias

| Camada | Stack |
|---|---|
| Backend | Python 3, Flask 3.1, Flask-SQLAlchemy 3.1, Flask-Migrate/Alembic, Flask-CORS, Flask-SocketIO 5.7 |
| Tempo real | WebSocket via `simple-websocket` (modo `threading`), fallback HTTP polling |
| Banco | PostgreSQL (`psycopg2-binary`); SQLite aceitável para testes/experimento |
| Frontend | JavaScript ES modules, CSS custom properties, Chart.js 4.4.7 (vendorizado) |
| Testes | pytest 8 + pytest-timeout |
| Produção | `wsgi.py` para um WSGI server (ex.: `gunicorn wsgi:app`) |

---

## Estrutura de diretórios

```
app.py                 Runner local + registro de blueprints, handlers e showcase
wsgi.py                Ponto de entrada de produção
cli.py                 Comandos `flask demo …`
models/                SQLAlchemy: locais, hospitais (flag demo), setores,
                       atendimentos (máquina de estados), base_model
routes/                main.py (páginas) · api.py (REST + webhook)
services/              atendimentos · metricas (coalescing + projeção do painel)
                       · realtime (salas, CAMPOS_PAINEL, snapshot)
                       · showcase (gerador sintético isolado)
utils/                 db · settings (env, TIMEZONE) · socket · tz · blueprints
templates/             index.html (painel de TV) · erro.html
static/css/style.css   Design tokens, temas claro/escuro e grade do painel
static/js/             main.js · state.js · api.js · realtime.js · relogio.js
static/js/ui/          multiselect · kpis · filas · espera · atendidos ·
                       graficos · alertas · hospitais · status · tema · dom
static/vendor/         chart.umd.min.js · socket.io.min.js
migrations/            Alembic (aditivo)
tests/                 conftest.py · test_api · test_atendimentos ·
                       test_metricas · test_realtime · test_showcase
docs/screenshots/      Capturas reais da interface
```

---

## Instalação

**Pré-requisitos:** Python 3.11+ e PostgreSQL (ou use SQLite para experimentar).

```bash
git clone git@github.com:<SEU-USUARIO>/medpulse.git
cd medpulse

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # opcional, para rodar os testes

cp .env.example .env              # edite os valores
flask db upgrade
python app.py
```

Acesse `http://127.0.0.1:5000/` — a raiz lista os locais cadastrados; o painel vive em `http://127.0.0.1:5000/<token-do-local>`.

Para criar um local e um hospital de demonstração do zero:

```bash
flask demo init --local "Clinica Exemplo" --backlog 40
flask demo listar
```

---

## Variáveis de ambiente

Todos os valores abaixo são nomes e exemplos ilustrativos — configure os reais no seu `.env`, que está no `.gitignore` e **não deve ser versionado**.

| Variável | Padrão | Descrição |
|---|---|---|
| `DEBUG` | `False` | Modo de depuração do Flask |
| `HOST` | `127.0.0.1` | Bind do runner local |
| `PORT` | `5000` | Porta do runner local |
| `SECRET` | — | Chave de sessão do Flask (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `DB_URI` | — | `postgresql+psycopg2://USUARIO:SENHA@HOST:5432/NOME_DO_BANCO` (ou `sqlite:///medpulse.db`) |
| `WEBHOOK_TOKEN` | vazio | Header `X-Webhook-Token` exigido no webhook. Vazio = endpoint aberto; **só em desenvolvimento** |
| `TIMEZONE` | `America/Sao_Paulo` | Fuso IANA da operação hospitalar. É a referência do relógio exibido no painel — a hora da TV não depende da máquina cliente |
| `SHOWCASE_ENABLED` | `false` | Liga/desliga o gerador sintético |
| `SHOWCASE_INTERVALO_MS` | `2600` | Intervalo base entre ciclos |
| `SHOWCASE_VELOCIDADE` | `6` | Escala as taxas de chegada/progressão (não o relógio real) |
| `SHOWCASE_MAX_ABERTOS` | `140` | Teto de atendimentos simultâneos abertos no hospital demo |
| `SHOWCASE_HOSPITAIS` | vazio | Allowlist de ids; vazio = todos os hospitais com `demo=True` |

---

## Execução

```bash
# Desenvolvimento (runner local com Socket.IO embutido)
python app.py

# Produção
gunicorn -k gthread -w 1 --threads 8 wsgi:app
```

Para pendurar na parede: suba com `HOST=0.0.0.0 python app.py`, aponte a TV para `http://<ip-do-servidor>:5000/<token-do-local>`, escolha o hospital no seletor e acione o botão de tela cheia. Nada mais precisa ser tocado — os agregados chegam pelo WebSocket e o relógio vem do servidor.

> O runner local usa `allow_unsafe_werkzeug` quando `DEBUG=False` apenas para permitir a demonstração com uma linha de comando. Em produção, sirva `wsgi.py` por um WSGI server e use uma fila de mensagens (Redis) se escalar para múltiplos workers.

### Showcase: como ligar e desligar

O gerador é **totalmente opcional** e não altera o comportamento normal da aplicação quando desligado.

```bash
# Ligar (ambiente de demonstração)
SHOWCASE_ENABLED=true python app.py

# Desligar — o painel volta a ser puramente reativo
SHOWCASE_ENABLED=false python app.py
```

Avanço determinístico para gravações e testes, sem subir servidor:

```bash
flask demo tick --ciclos 30 --dt 4 --velocidade 6 --semente 42
flask demo limpar --hospital 3 --confirmar
```

**Como funciona.** A cada ciclo o gerador avança um delta de tempo e aplica, sobre o hospital demo:
- **Chegadas** por Poisson com `lam = fluxo_base × fator_diurno × pico × velocidade × Δt` — a curva diurna reproduz o ritmo de um pronto-socorro (menos de madrugada, picos no fim da tarde), com prioridade sorteada pela distribuição assistencial típica;
- **Progressão** por transição exponencial `p = 1 − exp(−Δt/τ)`, com τ por status e portões de tempo mínimo — um paciente não sai de `em_atendimento` antes do tempo assistencial plausível;
- **Movimentação entre setores** e conclusões, sempre através da mesma camada de serviços usada pelo webhook, portanto sujeita à mesma máquina de estados e à mesma propagação por WebSocket.

O `velocidade` escala taxas, não o relógio: com `SHOWCASE_VELOCIDADE=6` o painel mostra em 10 minutos o movimento de 1 hora real. O ruído é estável por `(protocolo, status)` apenas para τ e portões; as demais decisões usam um RNG compartilhado, o que evita padrões previsíveis e aleatoriedade sem sentido. Contadores, filas, gráficos e KPIs derivam dos mesmos eventos, então permanecem coerentes entre si.

**Isolamento (obrigatório por design).** Dados sintéticos só existem no ambiente demonstrativo:
1. `hospitais.demo` é a fronteira; o gerador escreve somente onde `demo=True`.
2. `ShowcaseIsolamento` aborta qualquer tentativa de atingir um hospital real, e `SHOWCASE_MAX_ABERTOS` limita o volume.
3. Allowlist explícita por `SHOWCASE_HOSPITAIS` quando você quiser restringir a um id.
4. Nenhuma informação pessoal ou clínica real é gerada — os pacientes têm nomes e protocolos fictícios.

Assim, hospitais reais continuam recebendo exclusivamente dados do webhook, e o painel demonstra a separação no card "Por unidade monitorada".

---

## Testes

```bash
pytest -q
```

47 testes em 5 arquivos (SQLite em arquivo + `SocketIOTestClient`):

| Arquivo | Escopo |
|---|---|
| `test_api.py` (11) | `/health`, `/config` (inclusive `fuso_horario`/`agora_utc`/`agora_local`), escopo de local (403/404), `/resumo`, projeção agregada do painel, webhook autenticado |
| `test_atendimentos.py` (12) | Máquina de estados, updates parciais, idempotência, guarda de ordem, `409` em transição inválida |
| `test_metricas.py` (7) | Séries horárias, faixas de espera, coalescing de indicadores, contagem de filas, breakdown por hospital |
| `test_realtime.py` (5) | Salas por hospital, snapshot, eventos de novo/atualizado/resumo e **ausência de campos pessoais no payload** |
| `test_showcase.py` (12) | Isolamento, respeito às transições, teto de abertos, determinismo por semente, coerência de contadores |

Validação manual executada além da suíte, com Playwright (Chromium e Firefox reais) contra Flask + PostgreSQL e o gerador ativo, em viewport 1920×1080:

- **Zero rolagem** em tema escuro, tema claro, tela cheia (ambos os temas) e estado offline — excedente vertical e horizontal medidos em 0 px, nenhuma elemento com `overflow` residual e nenhum cartão cortado.
- **Dropdown real no Firefox**: abre com clique do mouse, `position: fixed`, retângulo dentro do viewport, o *hit-test* cai sobre o próprio painel suspenso, checkbox e rótulo alternam uma única vez, clique fora fecha, `Escape` fecha e `Enter` no gatilho abre — zero erros de página.
- **Tela cheia** com `document.fullscreenElement === painel`, fundo do cartão pintado (sem `<main>` preto) e o dropdown re-parenteado para o elemento em tela cheia, continua utilizável.
- **Isolamento por unidade**: com a demo desmarcada, todos os contadores zeram e o card "Por unidade monitorada" lista exatamente as unidades selecionadas. Trocar a seleção em rajada (marcar/desmarcar vários hospitais seguidos) também não mistura: cada agregado carrega o escopo com que foi calculado e o store descarta o que não é mais da seleção atual.
- **Privacidade**: varredura de todas as respostas `/api/*` capturadas durante a sessão não encontra `paciente`, `protocolo`, `cpf`, `documento`, `setor_id` ou `nome_paciente`; e os termos não aparecem no texto da tela.
- **Conexão**: ao derrubar o servidor, o selo vira `Offline` com a faixa de aviso; ao voltar, `Online` com snapshot novo — sem duplicatas e sem estados intermediários.
- **Relógio**: formatação no fuso do servidor, avança entre sincronizações e sobrevive ao reload com o tema persistido.

---

## Resoluções de tela

O layout é uma grade fixa de três colunas × duas linhas, calculada para preencher o viewport sem rolagem: em 1920×1080 e em qualquer resolução maior a unidade `rem` escala por `clamp(13px, .55vw + 6px, 26px)`, os cartões ganham altura e nada sai da tela. Medido com Playwright, com excedente de scroll lido no próprio documento:

| Viewport | Rolagem vertical | Rolagem horizontal | `rem` base |
|---|---|---|---|
| 3840×2160 (4K) | 0 px | 0 px | 26 px |
| 1920×1080 (Full HD) | 0 px | 0 px | 16,6 px |
| 1366×768 (notebook) | 0 px | 0 px | 13,5 px |

Abaixo de 1500 px os rodapés dos KPIs somem e abaixo de 1200 px relógio e rótulos dos botões entram em colapso, para caber. Abaixo de 1000 px a grade de três colunas não cabe mais: nesse intervalo, documentado de propósito, `.conteudo` volta a rolar. Um painel de TV nunca chega lá — ele apenas deixa de quebrar se alguém abrir a URL no celular.

![Abaixo de 1000 px o painel volta a rolar](docs/screenshots/painel-mobile.png)

---

## Limitações conhecidas

- **Runner local é single-thread por design de demonstração.** Com `gunicorn` multi-worker o Socket.IO precisa de um *message queue* (Redis) para distribuir eventos entre processos — não configurado aqui.
- **Coalescing introduz latência de ~0,6 s nos agregados.** Deliberado: evita recálculos redundantes sob rajadas de eventos. Eventos individuais de atendimento não passam por ele.
- **`cors_allowed_origins="*"`** e **`WEBHOOK_TOKEN` vazio** são conveniência de desenvolvimento. Em qualquer implantação real, restrinja as origens e defina o token.
- **`resumo.setores` continua no payload** embora o painel não o exiba mais: os demais consumidores do `/api/resumo` (e a suíte de testes) ainda usam esse bloco, e ele é agregado por setor — não contém dado de paciente. Remover é uma mudança de contrato do backend, propositalmente adiada.
- **`kpis.projecao_fila_min` é sensível ao throughput.** A projeção divide a fila pelo número de conclusões da janela; em um período com poucas conclusões o valor fica alto e é exibido como `—` quando não há nenhuma.
- **Série horária tem buckets de 1 h.** Variações menores que uma hora aparecem apenas nos contadores instantâneos.
- **Nomes de pacientes só existem no banco.** Eles são fictícios mesmo no showcase e nunca são serializados para o painel (`CAMPOS_PAINEL`).

## Próximos passos

- Autenticação por local (token assinado + expiração) e RBAC para operadores.
- Testes de performance de ponta a ponta e métricas de latência de eventos.
- Empacotar o front com build mínimo (ESBuild) e testes de componente no navegador.
- Suporte a múltiplos turnos e comparação dia a dia nos gráficos.
- Message queue Redis para produção multi-worker.
- Retirar `setores` do payload de painel quando o contrato do `/api/resumo` for revisado.

---

## Licença

MIT — ver [LICENSE](LICENSE).
