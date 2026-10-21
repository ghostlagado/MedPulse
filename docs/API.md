# API

Tudo sob `/api`. As respostas são JSON e sempre carregam `ok: true` no caminho feliz; no erro, `{"ok": false, "erro": "...", "codigo": "..."}`.

## Escopo e multi-tenancy

| Parâmetro | Efeito |
|---|---|
| `hospitais` | Lista de ids (separada por vírgula ou repetida). Vazio = todas as unidades ativas do local |
| `local` | Token UUID do local. Restringe a consulta ao que aquele tenant possui |

Quem passa um `local` e pede hospital de outro tenant recebe `403`; local inexistente é `404`. A regra está em `_restringir_ao_local()` ([routes/api.py:33](../routes/api.py#L33)) e vale para `/resumo`, `/atendimentos` e `/hospitais`.

## Endpoints de leitura

### `GET /api/health`

```json
{ "ok": true, "banco": true, "showcase": false, "horario": "2026-10-19T14:00:00+00:00" }
```

`banco` resulta de um `select 1` — é o sinal de vida da conexão, não do processo.

### `GET /api/config`

Vocabulário do painel, para o frontend não duplicar regra nenhuma:

| Campo | Conteúdo |
|---|---|
| `statuses`, `prioridades`, `estados_finais` | Tuplas vindas de `models/atendimentos.py` |
| `transicoes` | Mapa `estado → [estados permitidos]` |
| `rotulos_status`, `rotulos_prioridade` | Rótulos de exibição em português |
| `fuso_horario`, `agora_utc`, `agora_local` | Relógio do servidor no fuso da operação |
| `showcase` | `habilitado`, `hospitais_demo`, `frequencia_ms` |

### `GET /api/locais/<token>`

Local + hospitais ativos, cada um com seus setores ativos. Usado pela página para montar o seletor antes do primeiro request.

### `GET /api/hospitais?hospitais=1,2&local=<token>`

Somente o registro das unidades (`id`, `nome`, `local_id`, `ativo`, `demo`).

### `GET /api/resumo?hospitais=…&horas=24`

O agregado que o painel consome. Uma única leitura do banco alimenta todos os blocos, então os cartões não divergem entre si.

| Bloco | Conteúdo |
|---|---|
| `hospitais` | O escopo com que o cálculo foi feito — o navegador descarta payload de escopo diferente da seleção atual |
| `gerado_em`, `janela_horas` | Carimbo UTC e janela usada |
| `kpis` | `aguardando`, `em_atendimento`, `atendidos_periodo`, `cancelados_periodo`, `total_abertos`, `espera_media_min`, `espera_max_min`, `permanencia_media_min`, `duracao_media_min`, `tempo_atendido_min`, `tempo_a_atender_min`, `projecao_fila_min`, `taxa_conclusao` |
| `por_status`, `por_prioridade` | Contagens por estado e por prioridade (`fila`, `em_atendimento`, `atendidos`) |
| `filas` | Cruzamento status × prioridade com `qtde` e `tempo_medio_min` |
| `serie` | 24 buckets horários com `novos`, `concluidos`, `fila` (o último é a hora corrente) |
| `tempo_na_fila` | Distribuição agregada por faixa: até 15 min, 15–30, 30–60, 1–2 h, 2–4 h, acima de 4 h, separando `fila` de `em_atendimento` |
| `por_hospital` | `aguardando`, `em_atendimento`, `atendidos_24h` por unidade da seleção |
| `setores` | Carga por setor (agregado; o painel de TV não exibe mais este bloco) |
| `alertas` | Regras avaliadas no servidor: `nivel` (`critico`/`alto`/`medio`), `titulo`, `descricao` |

### `GET /api/atendimentos?hospitais=…&status=…&limite=300&min_espera=…`

Fila de atendimentos serializada pela **mesma** projeção do socket (`CAMPOS_PAINEL` + rótulos + `minutos_no_sistema`). Abertos primeiro, ordenados por gravidade e antiguidade; as vagas restantes do `limite` são preenchidas com encerrados das últimas 24 h. O painel de TV não usa este endpoint — ele existe para integrações e depuração.

### `GET /api/atendimentos/<id>`

Registro único, também pela projeção segura.

## Webhook de ingestão

`POST /api/webhook/atendimentos` — aceita um objeto ou lista (máximo 500 itens). Exige `X-Webhook-Token` quando `WEBHOOK_TOKEN` está definido.

```bash
curl -sS -X POST http://127.0.0.1:5000/api/webhook/atendimentos \
  -H 'Content-Type: application/json' \
  -H 'X-Webhook-Token: SEU_TOKEN' \
  -d '{
        "protocolo": "ABC123",
        "hospital_id": 3,
        "paciente": "Casos fictícios",
        "status": "em_atendimento",
        "prioridade": "alta",
        "setor": "Triagem",
        "hora_inicio": "2026-10-19T13:40:00+00:00",
        "atualizado_em": "2026-10-19T13:41:00+00:00"
      }'
```

| Campo | Regra |
|---|---|
| `hospital_id` | Obrigatório, numérico |
| `protocolo` | Chave de idempotência (até 64 caracteres). Ausente = gerado como `<fonte>-<hex>` |
| `status` | Ausente = "não alterar" (ou `aguardando` na criação). Valor fora do vocabulário = `status_invalido` |
| `prioridade` | Ausente = "não alterar" (ou `sem_triagem` na criação) |
| `paciente` | Rótulo de exibição (até 120 caracteres). Nunca viaja para o navegador |
| `setor_id` / `setor` | Um dos dois; `setor` é resolvido por nome dentro do hospital |
| `hora_inicio`, `hora_final` | ISO-8601, normalizados para UTC |
| `atualizado_em` | Guarda de ordem: evento mais velho que o último estado aplicado é ignorado |

Semântica: primeiro envio cria (`acao: "criado"`); o mesmo `protocolo` atualiza (`"atualizado"`); `atualizado_em` antigo devolve `"ignorada"` sem gravar.

**Respostas**

| HTTP | Quando |
|---|---|
| `200` | Lote inteiro aceito |
| `207` | Parte aceita, parte rejeitada — `rejeitados[]` diz qual item e por quê |
| `401` | Token ausente ou inválido (`nao_autenticado`) |
| `413` | Mais de 500 itens (`lote_grande`) |
| `422` | JSON ausente, payload não-objeto, `hospital_id` faltando, status/prioridade inválidos |
| `409` | `transicao_invalida` (inclusive estado terminal) ou `protocolo_conflito` (protocolo de outro hospital) |

## Socket.IO

Transporte: `websocket` com fallback para `polling`; sala por hospital, `hospital:<id>`.

| Direção | Evento | Payload |
|---|---|---|
| cliente → servidor | `subscribe` | `{ hospitais: [id…], limite: 300 }` |
| servidor → cliente | `painel:snapshot` | `{ hospitais, resumo, atendimentos, emitido_em }` no connect e a cada re-subscribe |
| servidor → cliente | `atendimento:novo` / `atendimento:atualizado` | `{ acao, atendimento }` pela projeção segura |
| servidor → cliente | `resumo:atualizado` | O `resumo` recalculado para a seleção daquele cliente |

O snapshot no re-subscribe é o que torna a reconexão segura: o navegador reconcilia o estado sem duplicar linha e sem aplicar evento fora de ordem. Os agregados publicados aqui passam pelo coalescing de ~0,6 s; os eventos individuais de atendimento, não.

## Documentos relacionados

- [Arquitetura e decisões](ARQUITETURA.md)
- [Variáveis de ambiente](../CONTRIBUTING.md#variáveis-de-ambiente)
- [Privacidade e segurança](../SECURITY.md)
