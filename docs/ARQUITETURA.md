# Arquitetura

Camadas, fluxo de um evento e as decisões que explicam por que o projeto é feito assim.

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

## Fluxo de um evento

1. O sistema de origem publica no webhook — ou o gerador sintético cria o atendimento direto no banco, pela mesma camada de serviços.
2. [`services/atendimentos.py`](../services/atendimentos.py) valida a transição contra a máquina de estados do model, grava e marca o hospital como "sujo".
3. [`services/metricas.py`](../services/metricas.py) coalesce os recálculos: uma thread de fundo agrupa hospitais sujos por seleção distinta e recalcula indicadores, filas e distribuição de espera **uma vez** por janela (~0,6 s).
4. [`services/realtime.py`](../services/realtime.py) projeta o atendimento em `CAMPOS_PAINEL` e emite na sala do hospital (`atendimento:novo`, `atendimento:atualizado`, `resumo:atualizado`).
5. O navegador recebe, aplica no store e atualiza somente os componentes inscritos naquele canal.

A API é a única fonte de verdade dos agregados: o mesmo `metricas.resumo()` atende ao `GET /api/resumo`, ao snapshot do socket e à publicação de indicadores.

## Modelo de dados

| Model | Papel |
|---|---|
| [`models/locais.py`](../models/locais.py) | Tenant. `id` UUID, usado como token na URL (`/{token}`) |
| [`models/hospitais.py`](../models/hospitais.py) | Unidade monitorada; `ativo` e `demo` — `demo` é a fronteira do ambiente sintético |
| [`models/setores.py`](../models/setores.py) | Setores do hospital (`nome`, `sigla`), usados pela ingestão e pelos agregados internos |
| [`models/atendimentos.py`](../models/atendimentos.py) | Fato monitorado: `status`, `prioridade`, `hora_inicio`, `hora_final`, `atualizado_em`, `protocolo` e a máquina de estados |

`STATUS`, `TRANSICOES`, `ESTADOS_FINAIS` e `PRIORIDADES` vivem no model e são expostos por `GET /api/config` — ninguém mais declara vocabulário de fluxo.

## Máquina de estados

```
aguardando ──► triagem ──► em_atendimento ──► finalizado
     │             │              │
     └─────────────┴──────────────┴────────► cancelado
```

* `aguardando` → `triagem` | `em_atendimento` | `cancelado`
* `triagem` → `aguardando` | `em_atendimento` | `cancelado`
* `em_atendimento` → `aguardando` | `finalizado` | `cancelado`
* `finalizado` e `cancelado` são terminais

Transição inválida é rejeitada na borda com `409` — vale igual para o webhook e para o gerador, porque os dois passam por `services/atendimentos.registrar()`.

## Decisões relevantes

- **Sem segunda fonte de verdade no frontend.** O vocabulário vem de `/api/config`; o navegador não duplica regras de negócio, não agrega filas e não calcula durações a partir de campos locais — só formata o que a API entrega.
- **Privacidade na borda, não na camada de apresentação.** `CAMPOS_PAINEL` é a lista branca de campos que um atendimento pode atravessar para o navegador:

  ```python
  CAMPOS_PAINEL = ("id", "hospital_id", "status", "prioridade",
                   "hora_inicio", "hora_final", "atualizado_em")
  ```

  Nome, protocolo, documento e setor ficam no servidor. Expor um dado pessoal exigiria alterar o backend — não é questão de CSS.
- **Agregação no servidor.** KPI, matriz de prioridade, série horária e faixas de espera saem prontos da API: coerência entre cartões e escalabilidade.
- **Relógio com uma única referência.** [`utils/tz.py`](../utils/tz.py) + `TIMEZONE` definem `FUSO_HORARIO`; a API carimba `gerado_em`/`agora_utc`/`agora_local` e o navegador mantém apenas o deslocamento. A hora da TV é a hora do servidor, não a da máquina cliente.
- **Escopo de tenant aplicado na consulta.** `_restringir_ao_local()` (`routes/api.py`) retorna `404` para local inexistente e `403` para hospital que não pertence ao local informado.
- **Identidade visual própria.** CSS com design tokens derivados da logo (verde/azul), sem framework de UI; Chart.js e socket.io vendorizados em `static/vendor/` — nenhuma dependência de CDN.
- **Migrações estritamente aditivas** (Flask-Migrate/Alembic), seguras contra um banco compartilhado.

## Estrutura de diretórios

```
app.py                 Runner local + registro de blueprints, handlers e showcase
wsgi.py                Ponto de entrada de produção
cli.py                 Comandos `flask demo …`
models/                SQLAlchemy: locais, hospitais (flag demo), setores,
                       atendimentos (máquina de estados), base_model
routes/                main.py (páginas) · api.py (REST + webhook)
services/              atendimentos · metricas (coalescing + agregados)
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
docs/                  Esta documentação + screenshots/
```

## Documentos relacionados

- [API e webhook](API.md)
- [Interface do painel de TV](UI.md)
- [Ambiente de demonstração](DEMO.md)
- [Critérios de aceite e evidências](VALIDACAO.md)
- [Como contribuir](../CONTRIBUTING.md)
