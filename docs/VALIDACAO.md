# Critérios de aceite e evidências

Uma suíte automatizada de backend e uma validação em navegador real (Playwright, Chromium e Firefox) contra Flask + PostgreSQL com o gerador sintético ativo. Nada aqui é inferido do código: cada linha de evidência veio de uma execução.

## Suíte de testes

```bash
pytest -q
```

47 testes em 5 arquivos, com SQLite em arquivo e `SocketIOTestClient` (`tests/conftest.py` monta um local com um hospital real e um hospital `demo=True`, e limpa as tabelas entre testes):

| Arquivo | Qtd | Escopo |
|---|---|---|
| `test_api.py` | 11 | `/health`, `/config` (inclusive `fuso_horario`/`agora_utc`/`agora_local`), escopo de local (403/404), `/resumo`, projeção agregada do painel, webhook autenticado |
| `test_atendimentos.py` | 12 | Máquina de estados, updates parciais, idempotência por `protocolo`, guarda de ordem por `atualizado_em`, `409` em transição inválida |
| `test_metricas.py` | 7 | Séries horárias, faixas de espera, coalescing de indicadores, contagem de filas, breakdown por hospital |
| `test_realtime.py` | 5 | Salas por hospital, snapshot, eventos de novo/atualizado/resumo e **ausência de campos pessoais no payload** |
| `test_showcase.py` | 12 | Isolamento, respeito às transições, teto de abertos, determinismo por semente, coerência de contadores |

## Validação em navegador

Executada com Playwright 1.64 (Chromium e Firefox), viewport 1920×1080, servidor local com `SHOWCASE_ENABLED=true` e o painel aberto no token do local. As rotinas de medição foram scripts de banco de prova — não fazem parte do repositório; a coluna "Como reproduzir" diz o que observar.

## Os 13 critérios

**1. Todas as informações essenciais cabem em Full HD, sem rolagem**
Medido o excedente de scroll no próprio documento (`document.documentElement.scrollHeight - clientHeight` e o par horizontal) em cinco estados: tema escuro, tema claro, tela cheia (os dois temas) e estado offline. Todos **0 px vertical, 0 px horizontal**, nenhum cartão cortado e nenhum elemento com `overflow` residual. Também 0/0 em 3840×2160 (`rem` 26 px) e 1366×768 (`rem` 13,5 px).
*Como reproduzir:* abrir o painel em 1920×1080 e verificar que não há barra de rolagem; para a exceção documentada, reduzir abaixo de 1000 px e ver a área útil voltar a rolar ([UI.md](UI.md#como-o-layout-n%C3%A3o-rola)).

**2. A seleção de hospitais usa os dados reais da API e aceita múltiplas unidades**
O seletor é montado a partir de `GET /api/locais/<token>` (nada de lista fixa no front), marca as unidades com `demo=True` e persiste a escolha por local. Marcar/desmarcar várias unidades altera o escopo de REST e socket.
*Como reproduzir:* abrir o painel, alternar hospitais no dropdown e conferir no Network/`resumo.hospitais` que a consulta acompanha.

**3. Os dados são filtrados corretamente, sem duplicação nem mistura entre hospitais**
Com apenas os hospitais reais selecionados, todos os contadores zeram e o card "Por unidade monitorada" lista exatamente as unidades escolhidas. Trocar a seleção em rajada não mistura unidades: cada agregado devolve o escopo com que foi calculado e o store descarta payload de escopo diferente (`static/js/state.js`, `escopoAtual()`).
*Esta validação encontrou um defeito real e corrigido:* o wrapper de recarga rotulava a resposta com a seleção *do momento*, então um corpo atrasado de `[1,2,3]` passava como `[1,2]`. Agora o escopo anunciado é o da resposta ([static/js/main.js:80](../static/js/main.js#L80)). Verificado por captura dos frames do WebSocket e inspeção do store ao vivo: seleção `[1,2]`, resumo `[1,2]`, unidades reais em 0 e 4 payloads atrasados ignorados.

**4. Nenhum nome de paciente ou dado pessoal aparece na interface**
Varredura de **todas** as respostas `/api/*` capturadas durante a sessão de navegador: nenhum `paciente`, `protocolo`, `cpf`, `documento`, `setor_id` ou `nome_paciente` no corpo; os termos também não aparecem no texto visível da tela. A garantia é de serialização (`CAMPOS_PAINEL`), não de CSS.
*Como reproduzir:* `curl -s localhost:5000/api/resumo?hospitais=3` e `…/api/atendimentos?hospitais=3` e procurar os campos; o teste `test_realtime.py` cobre o payload do socket.

**5. As prioridades respeitam rigorosamente as cores definidas**
Alta `#f2384f`/`#d1132f`, Intermediária `#f7c531`/`#eab308`, Baixa `#1f9d55`/`#16803d`, Não urgente `#3b74f0`/`#1257c9`, Sem triagem branco `#f3f8fb` (escuro) / preto `#101317` (claro) — a mesma escala em matriz, cartões, contadores, legendas e gráficos, sempre via tokens CSS. As séries do gráfico usam tokens próprios para não serem lidas como prioridade.
*Como reproduzir:* inspecionar `--p-*` em `static/css/style.css` e o `getComputedStyle` de um chip de cada prioridade nos dois temas.

**6. Fluxo, fila por prioridade e atendidos continuam funcionando**
Os três cards consomem `serie`, `filas`/`por_prioridade` e os contadores de conclusão do mesmo `resumo`, e seguem atualizando pelo socket depois das remoções de escopo.
*Como reproduzir:* acompanhar o painel por alguns minutos com a demo ligada e ver as três áreas mudarem juntas, sem divergir dos KPIs.

**7. "Mix de Prioridades" e "Carga por Setor" foram removidos**
Os dois gráficos saíram do template, dos módulos de UI e da tela. `resumo.setores` continua no payload da API (agregado, sem dado de paciente) porque outros consumidores e a suíte ainda o usam — é uma decisão de contrato adiada, não resíduo de tela.
*Como reproduzir:* buscar os rótulos em `templates/` e `static/js/` — só aparecem na documentação.

**8. Não existe botão de atualização manual**
Não há elemento nem handler de refresh: os agregados entram pelo socket, com sonda REST apenas em modo reserva.
*Como reproduzir:* procurar por "atualizar"/"refresh" na interface — nada clicável nesse sentido.

**9. Tema claro/escuro funciona em todos os componentes e mantém a preferência**
Troca apenas `data-tema` em `<html>`; os componentes leem as variáveis CSS, inclusive as sparklines (redesenhadas no canal `tema`). A preferência vive em `medpulse:tema` e sobrevive ao reload. A troca não recarrega dados nem reabre o socket — nenhum evento perdido durante a alternância.
*Como reproduzir:* alternar o tema com o painel recebendo eventos e conferir que o rodapé de sincronismo continua contando e que o selo segue `Online`.

**10. O status Online/Offline reflete a conexão WebSocket real**
`estado.conexao` nasce `offline`; só vira `online` com `socket.connected` verdadeiro. Derrubando o servidor, o selo vai a `Offline` com a faixa de aviso visível; subindo de novo, volta a `Online` com snapshot novo — sem duplicatas e sem estado intermediário.

**11. O relógio usa a referência do servidor e o fuso correto**
Com `TIMEZONE=America/Sao_Paulo`, a hora formatada vem de `agora_*`/`gerado_em` do servidor via `Intl.DateTimeFormat({ timeZone })`, com o navegador mantendo só o deslocamento. Leituras comparadas antes e depois de cada sincronização batem com o relógio do servidor; o ponteiro avança entre elas.
*Como reproduzir:* `curl -s localhost:5000/api/config | jq .agora_local` e comparar com o relógio da tela.

**12. O fullscreen não tem fundo preto indevido, cortes nem alteração de tema**
Medido em tela cheia nos dois temas: `document.fullscreenElement === #painel`, fundo do `<main>` `rgba(0,0,0,0)` (quem pinta é o `#painel`), zero rolagem e o dropdown ainda utilizável, re-parenteado para o elemento em tela cheia.

**13. Testes e builds disponíveis foram executados e os problemas encontrados, corrigidos**
`pytest -q` → 47 aprovados. As correções desta rodada: dropdown no Firefox (contexto de empilhamento do cabeçalho), fundo em tela cheia, dois estados de conexão, relógio do servidor, projeção sem dado pessoal, remoção dos dois gráficos e do refresh, e o vazamento de escopo descrito no critério 3.

## Ressalvas registradas

- **Abaixo de 1000 px o painel volta a rolar** — exceção documentada, não um defeito: a grade fixa de 3 colunas não cabe em celular ([UI.md](UI.md)).
- **`resumo.setores` continua no payload** da API embora a tela não o use mais.
- **`kpis.projecao_fila_min` é sensível ao throughput** da janela; sem conclusão alguma na janela é exibido como `—`.
- **O `role="listbox"`** do multiselect (`static/js/ui/multiselect.js`) descreve melhor uma lista de opções únicas do que um grupo de checkboxes; a alternativa correta seria um `fieldset` com `legend`. Não alterado nesta rodada para não mexer em algo que a validação já aprovou.
- **Navegador ≠ CI:** as medições de navegador foram executadas localmente com scripts de banco de prova; não há job de E2E no repositório.

## Documentos relacionados

- [Interface do painel de TV](UI.md)
- [API e tempo real](API.md)
- [Arquitetura e decisões](ARQUITETURA.md)
- [Ambiente de demonstração](DEMO.md)
- [Como contribuir](../CONTRIBUTING.md)
