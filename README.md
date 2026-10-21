# MedPulse

Painel de triagem hospitalar para TV: um mural de monitoramento contínuo que mostra o fluxo de atendimentos em tempo real — sem rolagem, sem interação operacional e sem nenhum dado de paciente.

O projeto parte de um wireframe e entrega uma interface de nível comercial sobre uma API Flask, um banco relacional e um WebSocket, com um **ambiente de demonstração autônomo** (hospital sintético "UBA Londres") que gera movimento contínuo e verossímil para apresentação pública e portfólio.

![Painel MedPulse em Full HD](docs/screenshots/painel-desktop.png)

## O que o painel faz

- **Seis indicadores no topo** — aguardando triagem, em atendimento, atendidos no período, espera média (com o tempo do atendimento mais antigo na fila), tempo em atendimento e projeção da fila, cada um com sparkline da série recente.
- **Fila por prioridade × etapa**, **fluxo de atendimento** (chegadas × conclusões × fila por hora), **distribuição agregada do tempo de espera** por faixa, **atendidos por prioridade** e **alertas de triagem** com regras avaliadas no servidor.
- **Nada rola** em 1920×1080 (e em qualquer resolução maior), medido em cinco estados da interface: excedente vertical e horizontal de 0 px, nenhum cartão cortado.
- **Quatro controles apenas**: seleção de hospitais, relógio, tema claro/escuro e tela cheia. O estado de conexão é um selo, não um botão — e não existe atualização manual.
- **Privacidade por construção**: nomes, protocolos, documentos e setor **não chegam ao navegador**. A projeção `CAMPOS_PAINEL` define o único conjunto de campos que atravessa a borda, então não é questão de CSS.
- **Multi-tenant**: escopo por *local* via token na URL (`/{token}`), multiselect de um ou mais hospitais com atalhos "Todos / Somente demo", e cada agregado devolve o escopo com que foi calculado — respostas fora de ordem são descartadas em vez de misturar unidades.
- **Tempo real**: Socket.IO por sala `hospital:<id>`, snapshot no connect e no re-subscribe, reconexão com backoff e modo reserva por REST. Selo **Online/Offline** sem zona cinzenta: página carregada não conta como conexão.
- **Relógio do servidor**: a referência é o fuso da operação (`TIMEZONE`), não o da TV; o navegador mantém apenas o deslocamento.
- **Showcase sintético isolado**: gerador com curva de chegada diurna e progressão exponencial por prioridade, escrevendo só em hospitais `demo=True`, ligável por variável de ambiente.

![Tela cheia](docs/screenshots/painel-tela-cheia.png)

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Camadas, fluxo de um evento, modelo de dados, máquina de estados e decisões relevantes |
| [docs/API.md](docs/API.md) | Endpoints REST, escopo de tenant, contrato do webhook, códigos de erro e eventos Socket.IO |
| [docs/UI.md](docs/UI.md) | Layout de TV, controles, paleta de prioridade, tema, fullscreen, dropdown no Firefox e resoluções medidas |
| [docs/DEMO.md](docs/DEMO.md) | Ambiente de demonstração: ligar/desligar, CLI `flask demo`, modelo do gerador, isolamento e roteiro de apresentação |
| [docs/VALIDACAO.md](docs/VALIDACAO.md) | Os 13 critérios de aceite com a evidência medida e como reproduzir cada um |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Setup, variáveis de ambiente, migrações, testes, convenções e fluxo de mudança |
| [SECURITY.md](SECURITY.md) | Postura de privacidade, superfície exposta, checklist de implantação e canal de reporte |

## Começar rápido

Pré-requisitos: Python 3.11+ e PostgreSQL (ou SQLite para experimentar).

```bash
git clone https://github.com/ghostlagado/MedPulse.git
cd MedPulse

python -m venv venv
source venv/bin/activate              # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # opcional, para os testes

cp .env.example .env                  # edite os valores
flask db upgrade
python app.py
```

Acesse `http://127.0.0.1:5000/` — a raiz mostra o primeiro local cadastrado; o painel vive em `http://127.0.0.1:5000/<token-do-local>`.

Para criar um local e um hospital de demonstração do zero, e ver o painel se mover sozinho:

```bash
flask demo init --local "Clinica Exemplo" --backlog 40
SHOWCASE_ENABLED=true python app.py
```

Para pendurar na parede: suba com `HOST=0.0.0.0 python app.py`, aponte a TV para `http://<ip-do-servidor>:5000/<token-do-local>`, escolha o hospital no seletor e acione o botão de tela cheia. Nada mais precisa ser tocado — os agregados chegam pelo WebSocket e o relógio vem do servidor.

As variáveis de ambiente (`SECRET`, `DB_URI`, `WEBHOOK_TOKEN`, `TIMEZONE` e as cinco `SHOWCASE_*`) estão na tabela de [CONTRIBUTING.md](CONTRIBUTING.md#variáveis-de-ambiente); `.env` é ignorado pelo git e **não deve ser versionado**.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3, Flask 3.1, Flask-SQLAlchemy 3.1, Flask-Migrate/Alembic, Flask-CORS, Flask-SocketIO 5.7 |
| Tempo real | WebSocket via `simple-websocket` (modo `threading`), fallback HTTP polling |
| Banco | PostgreSQL (`psycopg2-binary`); SQLite aceitável para testes/experimento |
| Frontend | JavaScript ES modules, CSS custom properties, Chart.js 4.4.7 (vendorizado) |
| Testes | pytest 8 + pytest-timeout; validação de interface com Playwright (Chromium e Firefox) |
| Produção | `wsgi.py` para um WSGI server (ex.: `gunicorn -k gthread -w 1 --threads 8 wsgi:app`) |

## Testes

```bash
pytest -q
```

47 testes em 5 arquivos (SQLite em arquivo + `SocketIOTestClient`), cobrindo API e escopo de tenant, máquina de estados e idempotência do webhook, agregados e coalescing, eventos em tempo real com **ausência de campos pessoais no payload** e isolamento do gerador. A validação de interface em navegador — rolagem zero, dropdown no Firefox, tela cheia, isolamento por unidade, privacidade, conexão e relógio — está medida em [docs/VALIDACAO.md](docs/VALIDACAO.md).

## Limitações conhecidas

- **Runner local é single-thread por design de demonstração.** Com `gunicorn` multi-worker o Socket.IO precisa de um *message queue* (Redis) para distribuir eventos entre processos — não configurado aqui.
- **Coalescing introduz latência de ~0,6 s nos agregados.** Deliberado: evita recálculos redundantes sob rajadas de eventos. Eventos individuais de atendimento não passam por ele.
- **`cors_allowed_origins="*"`** e **`WEBHOOK_TOKEN` vazio** são conveniência de desenvolvimento. Em qualquer implantação real, restrinja as origens e defina o token.
- **Sem autenticação de operadores**: o token de local é identificador de tenant, não credencial. O painel é de monitoramento, não de operação.
- **`resumo.setores` continua no payload** embora o painel não o exiba mais: os demais consumidores de `/api/resumo` (e a suíte de testes) ainda usam esse bloco, e ele é agregado por setor — não contém dado de paciente. Remover é uma mudança de contrato do backend, propositalmente adiada.
- **`kpis.projecao_fila_min` é sensível ao throughput.** A projeção divide a fila pelo número de conclusões da janela; em um período com poucas conclusões o valor fica alto e é exibido como `—` quando não há nenhuma.
- **Série horária tem buckets de 1 h.** Variações menores que uma hora aparecem apenas nos contadores instantâneos.
- **Abaixo de 1000 px o painel volta a rolar** — exceção documentada: a grade fixa de três colunas de TV não cabe em celular.

![Abaixo de 1000 px o painel volta a rolar](docs/screenshots/painel-mobile.png)

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
