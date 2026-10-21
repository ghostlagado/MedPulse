# Segurança e privacidade

O MedPulse é um painel de TV em espaço público: a tela é lida por quem passa, e o navegador pode ser uma smart TV compartilhada. O projeto trata isso como requisito de arquitetura, não como configuração.

## Postura de dados

**O navegador recebe agregados, não registros.** A única projeção de atendimento que atravessa a borda — REST, snapshot do socket e eventos — é definida por `CAMPOS_PAINEL`:

```python
# services/realtime.py
CAMPOS_PAINEL = ("id", "hospital_id", "status", "prioridade",
                 "hora_inicio", "hora_final", "atualizado_em")
```

`paciente`, `protocolo`, `setor_id` e qualquer outro campo de identificação ficam no servidor. O que a tela mostra no lugar de dados individuais é distribuição: faixas de tempo de espera, contagens por prioridade e por etapa.

Isso é uma garantia de serialização, não de CSS. Ocultar um campo que foi enviado continua sendo enviar o campo; para um dado pessoal aparecer na tela, alguém precisa alterar o backend — e os testes de `tests/test_realtime.py` cobrem justamente a ausência desses campos no payload.

**Escopo de tenant aplicado na consulta.** Um *local* é identificado pelo token UUID na URL; `_restringir_ao_local()` (`routes/api.py`) retorna `404` para local inexistente e `403` quando a consulta alcança um hospital de outro tenant. Vale para `/resumo`, `/atendimentos` e `/hospitais`, então não existe caminho de leitura transversal por parâmetro.

**Frontend não guarda estado de paciente.** `static/js/state.js` armazena indicadores, vocabulário e contadores; nenhum objeto de paciente existe no cliente, e a seleção persistida em `localStorage` é só a lista de ids de hospital por local.

**Dados clínicos não existem no projeto.** O campo `paciente` é um rótulo de exibição (até 120 caracteres) e não deve receber nome real; no ambiente de demonstração ele é sempre fictício, sorteado de listas fixas.

## Dados sintéticos não tocam dados reais

O gerador escreve exclusivamente em hospitais com `demo=True` e revalida a flag a cada ciclo, levantando `ShowcaseIsolamento` antes de persistir fora do ambiente demonstrativo. `SHOWCASE_HOSPITAIS` permite allowlist por id e `SHOWCASE_MAX_ABERTOS` limita o volume. Detalhes em [docs/DEMO.md](docs/DEMO.md).

## Superfície exposta

| Superfície | Controle | Risco se mal configurado |
|---|---|---|
| `POST /api/webhook/atendimentos` | `X-Webhook-Token` quando `WEBHOOK_TOKEN` está definido; lote ≤ 500; idempotência por `protocolo` | Escrita indevida de atendimentos — por isso o token é obrigatório na prática em qualquer implantação |
| Token UUID do local na URL | Escopo de leitura por tenant | É um identificador, **não** autenticação: quem o conhece vê os agregados daquele local |
| `GET /api/*` | Escopo por `local`/`hospitais`, projeção agregada | Sem token de local, as unidades ativas são visíveis entre si |
| Socket.IO | Sala `hospital:<id>`, projeção `CAMPOS_PAINEL` | `cors_allowed_origins="*"` aceita origem de qualquer página |

Não há autenticação de operadores nem RBAC: o painel é de monitoramento, não de operação. Controle de acesso por local (token assinado com expiração) e papéis estão listados como próximo passo — enquanto isso, a proteção real é de rede: o painel deve ser alcançável apenas pela rede do hospital.

## Checklist de implantação

Antes de pendurar na parede:

1. Defina `WEBHOOK_TOKEN` (nunca deixe vazio fora de desenvolvimento) e `SECRET` gerado, não o fallback `dev-secret-informe-no-env`.
2. Restrinja `CORS` à origem real em vez de `*`.
3. Sirva `wsgi.py` por um WSGI server (`gunicorn -k gthread -w 1 --threads 8 wsgi:app`) com `DEBUG=False`; multi-worker exige message queue (Redis) para o Socket.IO.
4. Banco com usuário de privilégios mínimos, `DB_URI` só no `.env`, migrações aditivas.
5. `SHOWCASE_ENABLED=false` em produção — dado sintético não pertence a um hospital real.
6. `TIMEZONE` no fuso IANA da operação (é a referência do relógio exibido).
7. HTTPS/reverse proxy na borda e acesso à URL do painel limitado à rede interna; o token do local na URL é segredo de fato.
8. Sem CDN: os assets de terceiros (`static/vendor/`) são vendorizados, então uma TV em rede isolada não puxa nada de fora.

## Segredos no repositório

`.env` está no `.gitignore`; `.env.example` só contém nomes e valores ilustrativos. Documentação, screenshots e testes usam tokens fictícios ou de teste — nenhuma captura expõe token de local real, credencial de banco ou header de webhook. Antes de publicar uma imagem da interface, confirme que a URL visível não revela um token de produção. Se um segredo for commitado, revogue-o (histórico reescrito não torna a credencial segura) e abra questão para limpeza.

## Reportar uma vulnerabilidade

Use um [security advisory privado](https://github.com/ghostlagado/MedPulse/security/advisories/new) em vez de issue pública. Inclua versão/commit, condição de reprodução e impacto; retorno esperado em poucos dias úteis. Mudanças em projeção de payload, escopo de tenant ou autenticação de webhook devem incluir teste que prove a garantia (o padrão está em `tests/test_realtime.py` e `tests/test_api.py`).

## Documentos relacionados

- [Arquitetura e decisões](docs/ARQUITETURA.md)
- [API e webhook](docs/API.md)
- [Interface do painel de TV](docs/UI.md)
- [Como contribuir](CONTRIBUTING.md)
