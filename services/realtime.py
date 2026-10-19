"""Eventos em tempo real (Socket.IO).

Modela uma sala por hospital e agrupa clientes por seleção idêntica, para que os
indicadores agregados sejam recalculados uma única vez por seleção suja. A API é a
fonte de verdade: o navegador nunca recalcula médias, apenas recebe o resultado.
"""

import logging
import threading

from flask import request

from utils.socket import socket
from utils.tz import agora_utc
from services import metricas

EVENTO_NOVO = "atendimento:novo"
EVENTO_ATUALIZADO = "atendimento:atualizado"
EVENTO_RESUMO = "resumo:atualizado"
EVENTO_SNAPSHOT = "painel:snapshot"

# Intervalo mínimo entre recálculos: agrupa rajadas de eventos (o showcase gera
# vários atendimentos por segundo) em uma única atualização de indicadores.
INTERVALO_INDICADORES = 0.6

log = logging.getLogger("medpulse.realtime")

_lock = threading.RLock()
_inscricoes = {}        # sid -> frozenset(hospital_id)
_sujos = set()          # hospital_id com mudança pendente
_parado = threading.Event()
_app = None
_trabalhador = None


def sala(hospital_id):
    return f"hospital:{hospital_id}"


def tem_clientes():
    with _lock:
        return bool(_inscricoes)


# Projeção enviada ao navegador: apenas o necessário para as métricas agregadas de
# triagem (tempo, quantidade, prioridade e status). Nome do paciente, protocolo e
# alocação de setor são dados identificáveis e nunca atravessam para o painel.
CAMPOS_PAINEL = (
    "id", "hospital_id", "status", "prioridade",
    "hora_inicio", "hora_final", "atualizado_em",
)


def serializar(atendimento):
    dados = {campo: getattr(atendimento, campo) for campo in CAMPOS_PAINEL}
    for campo in ("hora_inicio", "hora_final", "atualizado_em"):
        valor = dados.get(campo)
        if hasattr(valor, "isoformat"):
            dados[campo] = valor.isoformat()
    dados["hospital_nome"] = atendimento.hospital.nome if atendimento.hospital else None
    dados["status_label"] = metricas.ROTULOS_STATUS.get(atendimento.status, atendimento.status)
    dados["prioridade_label"] = metricas.ROTULOS_PRIORIDADE.get(
        atendimento.prioridade or "sem_triagem", atendimento.prioridade
    )
    return dados


def emitir_atendimento(atendimento, acao):
    """Publica a mudança na sala do hospital e marca os indicadores para recálculo."""
    evento = {"criado": EVENTO_NOVO, "atualizado": EVENTO_ATUALIZADO}.get(acao)
    if evento:
        socket.emit(
            evento,
            {"acao": acao, "atendimento": serializar(atendimento)},
            to=sala(atendimento.hospital_id),
            skip_sid=True,
        )
    marcar_sujo(atendimento.hospital_id)


def marcar_sujo(hospital_id):
    with _lock:
        _sujos.add(int(hospital_id))


def selecoes_sujas(sujos):
    """Retorna {selecao: [sid, ...]} das seleções afetadas pelos hospitais sujos."""
    grupos = {}
    for sid, selecao in _inscricoes.items():
        if sujos & set(selecao):
            grupos.setdefault(selecao, []).append(sid)
    return grupos


def publicar_resumos():
    with _lock:
        sujos = set(_sujos)
        _sujos.clear()
        grupos = selecoes_sujas(sujos)
    for selecao, sids in grupos.items():
        resumo = metricas.resumo(hospital_ids=sorted(selecao))
        socket.emit(EVENTO_RESUMO, resumo, to=list(sids), skip_sid=True)


def _ciclo():
    while not _parado.wait(INTERVALO_INDICADORES):
        try:
            with _app.app_context():
                publicar_resumos()
        except Exception:
            log.exception("falha ao publicar indicadores")


def registrar_handlers(app):
    global _app, _trabalhador
    _app = app

    @socket.on("connect")
    def on_connect(auth=None):
        return True

    @socket.on("disconnect")
    def on_disconnect():
        with _lock:
            _inscricoes.pop(request.sid, None)

    @socket.on("subscribe")
    def on_subscribe(data=None):
        from services import atendimentos as svc

        hospitais = {int(h) for h in (data or {}).get("hospitais", []) if str(h).isdigit()}
        limite = int((data or {}).get("limite", 300))
        sid = request.sid

        with _lock:
            anteriores = _inscricoes.get(sid, frozenset())
            _inscricoes[sid] = frozenset(hospitais)
        atualizar_salas(anteriores, hospitais)

        snapshot = {
            "hospitais": sorted(hospitais),
            "resumo": metricas.resumo(hospital_ids=sorted(hospitais)),
            "atendimentos": svc.listar(hospital_ids=sorted(hospitais), limite=limite),
            "emitido_em": agora_utc().isoformat(),
        }
        socket.emit(EVENTO_SNAPSHOT, snapshot, to=sid)

    if _trabalhador is None:
        _trabalhador = threading.Thread(target=_ciclo, name="medpulse-indicadores", daemon=True)
        _trabalhador.start()


def atualizar_salas(anteriores, atuais):
    """Ajusta as salas do cliente; deve ser chamada dentro de um handler Socket.IO."""
    from flask_socketio import join_room, leave_room

    for h in sorted(atuais):
        join_room(sala(h))
    for h in sorted(set(anteriores) - set(atuais)):
        leave_room(sala(h))


def parar():
    _parado.set()
