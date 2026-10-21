# Como contribuir

Configuração do ambiente de desenvolvimento, convenções do projeto e o fluxo de mudança. Leia [docs/ARQUITETURA.md](docs/ARQUITETURA.md) antes de mexer em services ou models — a maioria das regras abaixo existe para proteger as decisões de lá.

## Setup

Pré-requisitos: Python 3.11+, PostgreSQL (ou SQLite para experimentar) e um ambiente virtual.

```bash
git clone https://github.com/ghostlagado/MedPulse.git
cd MedPulse

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

cp .env.example .env              # preencha os valores do seu ambiente
flask db upgrade
python app.py
```

`flask` encontra o `app` em `app.py` sozinho (não há *app factory*, o objeto é global). A raiz `http://127.0.0.1:5000/` mostra o primeiro local cadastrado; o painel vive em `http://127.0.0.1:5000/<token-do-local>`, onde o token é o `id` UUID do local.

Para subir do zero sem banco configurado, troque `DB_URI` por `sqlite:///medpulse.db` no `.env`. Para criar um local com hospital de demonstração:

```bash
flask demo init --local "Clinica Exemplo" --backlog 40
flask demo listar
```

## Variáveis de ambiente

O `.env` está no `.gitignore` e **nunca deve ser versionado**. Preencha só nomes/valores ilustrativos em `.env.example`; se adicionar uma configuração, documente as duas coisas (arquivo e a tabela em [README](README.md#variáveis-de-ambiente)).

| Variável | Padrão | Descrição |
|---|---|---|
| `DEBUG` | `False` | Modo de depuração do Flask |
| `HOST` | `127.0.0.1` | Bind do runner local |
| `PORT` | `5000` | Porta do runner local |
| `SECRET` | — | Chave de sessão do Flask (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `DB_URI` | — | `postgresql+psycopg2://USUARIO:SENHA@HOST:5432/NOME` ou `sqlite:///medpulse.db` |
| `WEBHOOK_TOKEN` | vazio | Header `X-Webhook-Token` exigido no webhook. Vazio = endpoint aberto; **só em desenvolvimento** |
| `TIMEZONE` | `America/Sao_Paulo` | Fuso IANA da operação: é a referência do relógio do painel, nunca o da máquina cliente |
| `SHOWCASE_ENABLED` | `false` | Liga/desliga o gerador sintético |
| `SHOWCASE_INTERVALO_MS` | `2600` | Intervalo base entre ciclos |
| `SHOWCASE_VELOCIDADE` | `6` | Escala taxas de chegada/progressão (não o relógio real) |
| `SHOWCASE_MAX_ABERTOS` | `140` | Teto de atendimentos simultâneos abertos no hospital demo |
| `SHOWCASE_HOSPITAIS` | vazio | Allowlist de ids; vazio = todos os hospitais com `demo=True` |

A leitura é tipada em [`utils/settings.py`](utils/settings.py) — adicionar variável é acrescentar a leitura ali, não espalhar `getenv` pelos módulos.

## Banco e migrações

```bash
flask db migrate -m "descrição do que mudou"
flask db upgrade
```

Migrações são **estritamente aditivas**: nada de `drop column`, `drop table` ou renomear coluna em uma migração. O banco pode estar compartilhado com outra implantação, e o contrato da API é consumido por integrações externas. Precisa remover uma coluna? Pare de usá-la, marque como depreciada na documentação e deixe a limpeza para uma mudança de contrato deliberada (é assim que `resumo.setores` continua no payload).

## Rodando e testando

```bash
# Desenvolvimento (runner local com Socket.IO embutido)
python app.py

# Produção
gunicorn -k gthread -w 1 --threads 8 wsgi:app

# Testes
pytest -q
```

A suíte usa SQLite em arquivo (`tests/_medpulse_test.db`, criado e removido pela fixture de sessão) e `SocketIOTestClient`; `tests/conftest.py` fixa o ambiente antes de importar `app`, porque o engine é criado na importação. Para rodar um arquivo: `pytest tests/test_metricas.py -q`.

Validação de interface é feita com Playwright (Chromium **e** Firefox — o dropdown do seletor é exatamente o tipo de coisa que só o Firefox quebra):

```bash
playwright install firefox        # uma vez por máquina
```

Os critérios medidos em navegador e como reproduzi-los estão em [docs/VALIDACAO.md](docs/VALIDACAO.md). Se sua mudança toca layout, tema, cores de prioridade, fullscreen, conexão ou relógio, ela precisa de medição — não de impressão: `scrollHeight` lido na página, `getComputedStyle` no componente, fuso comparado com `/api/config`.

## Convenções

**Python.** Camadas como já estão: `routes/` só orquestra request/response, `services/` concentra regra e agregação, `models/` declara dados e vocabulário de estado. Nada de query em route, nada de HTML em service. `from flask import current_app` em vez de importar o `app` global para dentro de services. Erros de negócio sobem como exceção de serviço (`ErroAtendimento` com `codigo` e `status_http`) e viram envelope JSON na borda.

**Identificadores e textos em português**, como o código existente (`hora_inicio`, `registrar`, `_restringir_ao_local`), com nomes de domínio, não abreviações inventadas. Docstring de módulo no topo de cada arquivo explicando o papel e o *porquê* da existência daquele módulo; comentário no corpo só quando o motivo não é óbvio (um *workaround*, uma invariant, uma escolha contraintuitiva).

**JavaScript.** ES modules sem build, um componente por arquivo em `static/js/ui/`, estado **somente** em `static/js/state.js`, REST em `static/js/api.js`, socket em `static/js/realtime.js`. Componentes se inscrevem nos canais de que precisam (`inscrever(['resumo', 'meta'])`) e se redesenham sozinhos; nada de re-render da árvore inteira nem de manipular DOM de outro módulo.

**CSS.** Só variáveis de tema (`--fundo`, `--surface`, `--texto-*`, `--p-*`); cor literal dentro de regra de componente é um defeito, porque quebra o tema claro. Medidas em `rem`/`clamp`, nunca altura fixa que empurre rolagem.

**Frontend não é segunda fonte de verdade.** Vocabulário de estados, rótulos, transições e agregados vêm da API (`/api/config`, `/api/resumo`). Não calcule média, duração ou contagem de fila no navegador, e não declare uma lista de status local.

## As três regras que não se negociam

1. **Nenhum dado pessoal atravessa a borda para o navegador.** A lista branca é `CAMPOS_PAINEL` ([services/realtime.py](services/realtime.py)); REST, snapshot e eventos passam pela mesma projeção. Ocultar com CSS não conta — esconder um campo que foi enviado continua sendo enviar o campo. Precisa de um novo campo na tela? Ele tem de ser agregado e seguro, e a alteração é no backend, com teste.
2. **Dado sintético não pisa em hospital real.** O gerador escreve só onde `demo=True`; qualquer mudança nele precisa manter `ShowcaseIsolamento`, o teto de abertos e a allowlist funcionando, e continuar passando pelos `tests/test_showcase.py`.
3. **Não se afirma que uma integração funciona sem tê-la executado.** Teste de API, banco, webhook e WebSocket juntos, não só o unit que passou.

## Fluxo de mudança

Branch a partir da `main` com prefixo de intenção (`feat/…`, `fix/…`, `docs/…`), um assunto por branch. Commits no estilo do histórico (`Feat: …`, `Fix: …`), pequenos e por arquivo/concern quando fizer diferença na revisão. Antes de abrir o PR:

```bash
pytest -q
python app.py    # e abrir o painel: estados de carregamento, vazio, offline e tela cheia
```

No PR, descreva o que mudou **e o que foi medido**, anexe captura real quando a mudança for visual (as imagens de `docs/screenshots/` têm que corresponder ao sistema implementado — sem mockup, sem tela que não existe), atualize a documentação afetada e liste pendências que dependem de fora (deploy, banco compartilhado, credencial).

## Armadilhas conhecidas

- **`.gitignore` tem a linha `tests/`** (herdada do template Python). Ela ignora o diretório de testes — se `git status` não mostrar um arquivo novo dentro de `tests/`, é por isso. O que deveria ser ignorado é só o banco da suíte: troque a linha por `/tests/_medpulse_test.db`.
- **Runner local é single-thread.** Com `DEBUG=False`, `app.py` usa `allow_unsafe_werkzeug` só para a demo rodar com um comando. Multi-worker precisa de *message queue* (Redis) para o Socket.IO distribuir eventos entre processos.
- **O runner não recarrega o gerador.** `showcase.iniciar()` roda na importação; com reloader ativo só o processo filho gera dados, para não duplicar chegadas.
- **Coalescing de ~0,6 s nos agregados.** Deliberado; eventos individuais de atendimento não passam por ele. Não "corrija" a latência recalculando a cada evento.
- **`cors_allowed_origins="*"` e `WEBHOOK_TOKEN` vazio** são conveniência de desenvolvimento, não configuração de produção.

## Segurança

Mudança que toque autenticação, token de webhook, projeção de payload ou dados de tenant leia [SECURITY.md](SECURITY.md) e reporte vulnerabilidade pelo canal descrito lá — não em issue pública.

## Documentos relacionados

- [README](README.md)
- [Arquitetura e decisões](docs/ARQUITETURA.md)
- [API e webhook](docs/API.md)
- [Interface do painel de TV](docs/UI.md)
- [Ambiente de demonstração](docs/DEMO.md)
- [Critérios de aceite e evidências](docs/VALIDACAO.md)
