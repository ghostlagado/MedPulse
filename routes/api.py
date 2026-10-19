"""API REST: consumo do painel, ingestão via webhook e metadados de configuração."""

from hmac import compare_digest

from flask import Blueprint, abort, current_app, jsonify, request

from utils.db import db, uuid_de
from utils.tz import agora_utc, para_local
from models.locais import Locais
from models.hospitais import Hospitais
from models.atendimentos import PRIORIDADES, STATUS, ESTADOS_FINAIS, TRANSICOES
from services import atendimentos as svc
from services import metricas

api_bp = Blueprint("api", __name__)


def _ids(nome="hospitais"):
    valores = request.args.getlist(nome)
    saida = []
    for bruto in valores:
        for parte in str(bruto).split(","):
            parte = parte.strip()
            if parte.isdigit():
                saida.append(int(parte))
    return sorted(set(saida))


def _local(token):
    return db.session.get(Locais, uuid_de(token)) if token else None


def _restringir_ao_local(ids, token):
    """Impede que uma consulta alcance hospitais de outro local (tenant)."""
    if token:
        local = _local(token)
        if not local:
            abort(404, description="local não encontrado")
        permitidos = {h.id for h in local.hospitais if h.ativo}
        if not ids:
            return sorted(permitidos)
        if set(ids) - permitidos:
            abort(403, description="hospital fora do local")
        return ids
    if not ids:
        return sorted(h.id for h in Hospitais.query.filter_by(ativo=True).all())
    return ids


def _erro(mensagem, codigo="invalido", status=422):
    return jsonify({"ok": False, "erro": mensagem, "codigo": codigo}), status


@api_bp.get("/health")
def health():
    try:
        db.session.execute(db.text("select 1"))
        banco = True
    except Exception:
        banco = False
    return jsonify({
        "ok": True,
        "banco": banco,
        "showcase": current_app.config.get("SHOWCASE_ENABLED", False),
        "horario": agora_utc().isoformat(),
    })


@api_bp.get("/config")
def config():
    fuso = current_app.config.get("FUSO_HORARIO", "UTC")
    agora = agora_utc()
    return jsonify({
        "ok": True,
        "statuses": list(STATUS),
        "prioridades": list(PRIORIDADES),
        "transicoes": {k: sorted(v) for k, v in TRANSICOES.items()},
        "estados_finais": sorted(ESTADOS_FINAIS),
        "rotulos_status": metricas.ROTULOS_STATUS,
        "rotulos_prioridade": metricas.ROTULOS_PRIORIDADE,
        # Relógio do painel: o navegador sincroniza o deslocamento e formata no fuso
        # da operação, nunca no fuso da máquina que abre a página.
        "fuso_horario": fuso,
        "agora_utc": agora.isoformat(),
        "agora_local": para_local(agora, fuso).isoformat(),
        "showcase": {
            "habilitado": bool(current_app.config.get("SHOWCASE_ENABLED")),
            "hospitais_demo": current_app.config.get("SHOWCASE_HOSPITAIS", []),
            "frequencia_ms": current_app.config.get("SHOWCASE_INTERVALO_MS"),
        },
    })


@api_bp.get("/locais/<uuid:token>")
def local(token):
    registro = _local(str(token))
    if not registro:
        abort(404)
    hospitais = []
    for h in registro.hospitais:
        if not h.ativo:
            continue
        hospitais.append({
            **h.to_dict(),
            "setores": [s.to_dict() for s in h.setores if s.ativo],
        })
    return jsonify({
        "ok": True,
        "local": {"id": str(registro.id), "nome": registro.nome},
        "hospitais": hospitais,
    })


@api_bp.get("/hospitais")
def hospitais():
    ids = _restringir_ao_local(_ids(), request.args.get("local"))
    registros = Hospitais.query.filter(Hospitais.id.in_(ids or [0]), Hospitais.ativo.is_(True)).all()
    return jsonify({
        "ok": True,
        "hospitais": [{**h.to_dict(), "demo": bool(h.demo)} for h in registros],
    })


@api_bp.get("/resumo")
def resumo():
    ids = _restringir_ao_local(_ids(), request.args.get("local"))
    horas = int(request.args.get("horas", metricas.JANELA_HORAS))
    return jsonify({"ok": True, **metricas.resumo(ids, horas=max(horas, 1))})


@api_bp.get("/atendimentos")
def atendimentos():
    ids = _restringir_ao_local(_ids(), request.args.get("local"))
    try:
        itens = svc.listar(
            hospital_ids=ids,
            status=request.args.get("status"),
            limite=int(request.args.get("limite", 300)),
            minutos_espera=request.args.get("min_espera"),
        )
    except svc.ErroAtendimento as erro:
        return _erro(str(erro), erro.codigo, erro.status_http)
    return jsonify({
        "ok": True,
        "gerado_em": agora_utc().isoformat(),
        "total": len(itens),
        "atendimentos": itens,
    })


@api_bp.get("/atendimentos/<int:atendimento_id>")
def atendimento(atendimento_id):
    registro = svc.obter(atendimento_id)
    if not registro:
        abort(404)
    from services import realtime
    return jsonify({"ok": True, "atendimento": realtime.serializar(registro)})


@api_bp.post("/webhook/atendimentos")
def webhook():
    """Ingestão do sistema de origem (HIS/ERP). Aceita um objeto ou lista;
    idempotente por `protocolo` e protegida contra eventos fora de ordem."""
    token_obrigatorio = current_app.config.get("WEBHOOK_TOKEN")
    if token_obrigatorio:
        recebido = request.headers.get("X-Webhook-Token", "")
        if not compare_digest(recebido, token_obrigatorio):
            return _erro("token do webhook inválido", "nao_autenticado", 401)

    payload = request.get_json(silent=True)
    if payload is None:
        return _erro("JSON obrigatório", "payload_invalido")

    itens = payload if isinstance(payload, list) else [payload]
    if len(itens) > 500:
        return _erro("lote máximo de 500 atendimentos", "lote_grande", 413)

    resultados = svc.registrar_lote(itens, fonte="webhook")
    aceitos = [r for r in resultados if r["ok"]]
    rejeitados = [r for r in resultados if not r["ok"]]
    status = 207 if rejeitados and aceitos else (200 if not rejeitados else 422)
    return jsonify({
        "ok": not rejeitados,
        "aceitos": len(aceitos),
        "rejeitados": rejeitados,
        "resultados": resultados,
    }), status
