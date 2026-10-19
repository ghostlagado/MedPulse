"""Escrita de atendimentos: caminho único usado pelo webhook, pela API e pelo
showcase. Centraliza validação, idempotência, guarda de ordem e máquina de
estados, de modo que nada no frontend ou no gerador replique essas regras."""

import uuid
from datetime import timedelta

from sqlalchemy import case

from utils.db import db
from utils.tz import agora_utc, para_utc
from models.atendimentos import (
    Atendimentos,
    PRIORIDADES,
    PRIORIDADE_SEM_TRIAGEM,
    STATUS,
    STATUS_AGUARDANDO,
    STATUS_CANCELADO,
    STATUS_EM_ATENDIMENTO,
    STATUS_FINALIZADO,
    STATUS_TRIAGEM,
    TRANSICOES,
    ESTADOS_FINAIS,
)
from models.hospitais import Hospitais
from models.setores import Setores
from services import realtime

ORDEM_PRIORIDADE = {
    "alta": 0,
    "intermediaria": 1,
    "baixa": 2,
    "nao_urgente": 3,
    "sem_triagem": 4,
}
ABERTOS = (STATUS_AGUARDANDO, STATUS_TRIAGEM, STATUS_EM_ATENDIMENTO)


class ErroAtendimento(ValueError):
    def __init__(self, mensagem, codigo="invalido", status_http=422):
        super().__init__(mensagem)
        self.codigo = codigo
        self.status_http = status_http


def _peso_prioridade():
    return case(
        *(
            (Atendimentos.prioridade == p, ORDEM_PRIORIDADE.get(p, 9))
            for p in PRIORIDADES
        ),
        else_=9,
    )


def validar(dados):
    if not isinstance(dados, dict):
        raise ErroAtendimento("Payload deve ser um objeto JSON.")
    hospital_id = dados.get("hospital_id")
    if hospital_id is None or not str(hospital_id).isdigit():
        raise ErroAtendimento("hospital_id numérico é obrigatório.", "hospital_obrigatorio")
    # Ausência de status/prioridade significa "não alterar" ao atualizar e
    # o valor inicial (aguardando / sem_triagem) ao criar.
    tem_status = dados.get("status") is not None
    tem_prioridade = dados.get("prioridade") is not None
    status = dados.get("status") or STATUS_AGUARDANDO
    if status not in STATUS:
        raise ErroAtendimento(f"status inválido: {status}", "status_invalido")
    prioridade = dados["prioridade"] if tem_prioridade else PRIORIDADE_SEM_TRIAGEM
    if prioridade not in PRIORIDADES:
        raise ErroAtendimento(f"prioridade inválida: {prioridade}", "prioridade_invalida")
    return {
        "hospital_id": int(hospital_id),
        "status": status,
        "tem_status": tem_status,
        "tem_prioridade": tem_prioridade,
        "prioridade": prioridade,
        "paciente": (str(dados["paciente"])[:120] if dados.get("paciente") else None),
        "protocolo": (str(dados["protocolo"])[:64] if dados.get("protocolo") else None),
        "hora_inicio": para_utc(dados["hora_inicio"]) if dados.get("hora_inicio") else None,
        "hora_final": para_utc(dados["hora_final"]) if dados.get("hora_final") else None,
        "atualizado_em": para_utc(dados["atualizado_em"]) if dados.get("atualizado_em") else None,
        "setor_id": dados.get("setor_id"),
        "setor_nome": dados.get("setor"),
    }


def _resolver_setor(hospital_id, setor_id, setor_nome):
    if setor_id in (None, ""):
        if not setor_nome:
            return None
        setor = (
            Setores.query.filter(
                Setores.hospital_id == hospital_id,
                db.func.lower(Setores.nome) == str(setor_nome).lower(),
            ).first()
        )
        if not setor:
            raise ErroAtendimento(f"setor desconhecido: {setor_nome}", "setor_invalido")
        return setor.id
    if not str(setor_id).isdigit():
        raise ErroAtendimento("setor_id deve ser numérico.", "setor_invalido")
    setor = Setores.query.filter_by(id=int(setor_id), hospital_id=hospital_id).first()
    if not setor:
        raise ErroAtendimento(f"setor {setor_id} não pertence ao hospital.", "setor_invalido")
    return setor.id


def registrar(dados, fonte="api"):
    """Cria ou atualiza um atendimento. Retorna (atendimento, acao) com
    acao em {'criado', 'atualizado', 'ignorada'}."""
    dados = validar(dados)
    agora = agora_utc()

    hospital = db.session.get(Hospitais, dados["hospital_id"])
    if not hospital:
        raise ErroAtendimento("hospital inexistente.", "hospital_inexistente", 404)
    setor_id = _resolver_setor(hospital.id, dados["setor_id"], dados["setor_nome"])

    protocolo = dados["protocolo"] or f"{fonte}-{uuid.uuid4().hex[:16]}"
    existente = Atendimentos.query.filter_by(protocolo=protocolo).first()

    if existente is None:
        novo = Atendimentos(
            protocolo=protocolo,
            hospital_id=hospital.id,
            setor_id=setor_id,
            paciente=dados["paciente"],
            prioridade=dados["prioridade"],
            status=dados["status"],
            hora_inicio=dados["hora_inicio"] or agora,
            hora_final=dados["hora_final"] if dados["status"] in ESTADOS_FINAIS else None,
            atualizado_em=dados["atualizado_em"] or agora,
        )
        if novo.status in ESTADOS_FINAIS and not novo.hora_final:
            novo.hora_final = agora
        db.session.add(novo)
        _commit()
        realtime.emitir_atendimento(novo, "criado")
        return novo, "criado"

    if existente.hospital_id != hospital.id:
        raise ErroAtendimento("protocolo já pertence a outro hospital.", "protocolo_conflito", 409)

    # Guarda de ordem: eventos mais antigos que o último estado aplicado são descartados.
    if dados["atualizado_em"] and existente.atualizado_em and \
            para_utc(dados["atualizado_em"]) <= para_utc(existente.atualizado_em):
        return existente, "ignorada"

    novo_status = dados["status"]
    if dados["tem_status"] and novo_status != existente.status:
        if existente.status in ESTADOS_FINAIS:
            raise ErroAtendimento(
                f"atendimento {existente.status} é terminal.", "transicao_invalida", 409
            )
        if novo_status not in TRANSICOES.get(existente.status, set()):
            raise ErroAtendimento(
                f"transição inválida: {existente.status} -> {novo_status}",
                "transicao_invalida", 409,
            )
        existente.status = novo_status
        if novo_status in ESTADOS_FINAIS:
            existente.hora_final = dados["hora_final"] or agora
        else:
            existente.hora_final = None

    if dados["tem_prioridade"]:
        existente.prioridade = dados["prioridade"]
    if dados["paciente"]:
        existente.paciente = dados["paciente"]
    if setor_id is not None:
        existente.setor_id = setor_id
    if dados["hora_inicio"]:
        existente.hora_inicio = dados["hora_inicio"]
    existente.atualizado_em = dados["atualizado_em"] or agora

    _commit()
    realtime.emitir_atendimento(existente, "atualizado")
    return existente, "atualizado"


def _commit():
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise ErroAtendimento("falha ao persistir atendimento.", "persistencia", 500)


def registrar_lote(itens, fonte="webhook"):
    """Processa um lote do webhook sem abortar os itens válidos."""
    resultados = []
    for item in itens or []:
        try:
            atendimento, acao = registrar(item, fonte=fonte)
            resultados.append({
                "ok": True,
                "acao": acao,
                "id": atendimento.id,
                "protocolo": atendimento.protocolo,
            })
        except ErroAtendimento as erro:
            db.session.rollback()
            resultados.append({"ok": False, "erro": str(erro), "codigo": erro.codigo})
    return resultados


def listar(hospital_ids=None, status=None, limite=300, minutos_espera=None):
    """Fila para a tabela do painel: abertos primeiro por gravidade/antiguidade,
    depois os encerrados mais recentes."""
    hospital_ids = sorted({int(h) for h in (hospital_ids or []) if str(h).isdigit()})
    limite = max(int(limite), 1)

    def base():
        consulta = Atendimentos.query
        if hospital_ids:
            consulta = consulta.filter(Atendimentos.hospital_id.in_(hospital_ids))
        return consulta

    agora = agora_utc()
    if status:
        if status not in STATUS:
            raise ErroAtendimento(f"status inválido: {status}", "status_invalido")
        linhas = base().filter(Atendimentos.status == status).order_by(
            _peso_prioridade(), Atendimentos.hora_inicio.desc()
        ).limit(limite).all()
    else:
        abertos = base().filter(Atendimentos.status.in_(ABERTOS)).order_by(
            _peso_prioridade(), Atendimentos.hora_inicio.asc()
        ).limit(limite).all()
        faltam = limite - len(abertos)
        encerrados = []
        if faltam > 0:
            encerrados = base().filter(
                Atendimentos.status.notin_(ABERTOS),
                Atendimentos.hora_final >= agora - timedelta(hours=24),
            ).order_by(Atendimentos.hora_final.desc()).limit(faltam).all()
        linhas = abertos + encerrados

    saida = []
    for a in linhas:
        item = realtime.serializar(a)
        inicio, fim = para_utc(a.hora_inicio), para_utc(a.hora_final)
        item["minutos_no_sistema"] = int(((fim or agora) - inicio).total_seconds() // 60) if inicio else None
        saida.append(item)
    if minutos_espera:
        saida = [s for s in saida if (s["minutos_no_sistema"] or 0) >= int(minutos_espera)]
    return saida


def obter(atendimento_id):
    return db.session.get(Atendimentos, int(atendimento_id))
