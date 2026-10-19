"""Cálculo dos indicadores do painel.

Uma única leitura do banco por requisição/agregação garante que KPIs, filas,
gráficos e alertas saiam do mesmo instantâneo de dados - nada de o frontend
recalcular médias por conta própria e divergir da API.
"""

from datetime import timedelta

from utils.db import db
from utils.tz import agora_utc, para_utc
from models.atendimentos import (
    Atendimentos,
    PRIORIDADES,
    STATUS,
    STATUS_AGUARDANDO,
    STATUS_CANCELADO,
    STATUS_EM_ATENDIMENTO,
    STATUS_FINALIZADO,
    STATUS_TRIAGEM,
)
from models.hospitais import Hospitais

JANELA_HORAS = 24
FILABERTA = (STATUS_AGUARDANDO, STATUS_TRIAGEM)
EM_FLUXO = FILABERTA + (STATUS_EM_ATENDIMENTO,)

ROTULOS_PRIORIDADE = {
    "alta": "Alta",
    "intermediaria": "Intermediária",
    "baixa": "Baixa",
    "nao_urgente": "Não urgente",
    "sem_triagem": "Sem triagem",
}
ROTULOS_STATUS = {
    "aguardando": "Aguardando",
    "triagem": "Em triagem",
    "em_atendimento": "Em atendimento",
    "finalizado": "Finalizado",
    "cancelado": "Cancelado",
}


def _minutos(duracao):
    return int(round(duracao.total_seconds() / 60)) if duracao else 0


def _media(vals):
    return int(round(sum(vals) / len(vals))) if vals else 0


def carregar(hospital_ids, horas=JANELA_HORAS):
    """Carrega o instantâneo: atendimentos abertos + concluídos nas últimas N horas."""
    hospital_ids = [int(h) for h in hospital_ids]
    if not hospital_ids:
        return []
    agora = agora_utc()
    desde = agora - timedelta(hours=horas)
    rows = (
        Atendimentos.query.filter(Atendimentos.hospital_id.in_(hospital_ids))
        .filter(
            db.or_(
                Atendimentos.status.in_(EM_FLUXO),
                Atendimentos.hora_final.isnot(None) & (Atendimentos.hora_final >= desde),
                Atendimentos.hora_inicio >= desde,
            )
        )
        .all()
    )
    for a in rows:
        a._hora_inicio = para_utc(a.hora_inicio)
        a._hora_final = para_utc(a.hora_final)
    return rows


def _fila(rows, agora):
    """Linha (status x prioridade) com qtde e tempo médio de permanência."""
    saida = []
    for status in STATUS:
        for prioridade in PRIORIDADES:
            grupo = [a for a in rows if a.status == status and (a.prioridade or "sem_triagem") == prioridade]
            if not grupo:
                continue
            if status in EM_FLUXO:
                tempos = [_minutos(agora - a._hora_inicio) for a in grupo]
            else:
                tempos = [_minutos(a._hora_final - a._hora_inicio) for a in grupo if a._hora_final]
            saida.append({
                "status": status,
                "status_label": ROTULOS_STATUS[status],
                "prioridade": prioridade,
                "prioridade_label": ROTULOS_PRIORIDADE[prioridade],
                "qtde": len(grupo),
                "tempo_medio_min": _media(tempos),
            })
    return saida


def _serie(rows, agora, horas=JANELA_HORAS):
    """Série horária: chegadas, conclusões e fila ao fim de cada hora.
    O último bucket é a hora corrente, para o gráfico terminar no 'agora' do painel."""
    inicio_serie = (agora - timedelta(hours=horas - 1)).replace(minute=0, second=0, microsecond=0)
    buckets = []
    for i in range(horas):
        momento = inicio_serie + timedelta(hours=i)
        limite = momento + timedelta(hours=1)
        novos = sum(1 for a in rows if a._hora_inicio and momento <= a._hora_inicio < limite)
        fins = sum(1 for a in rows if a._hora_final and momento <= a._hora_final < limite)
        fila = sum(
            1 for a in rows
            if a._hora_inicio and a._hora_inicio < limite
            and (a._hora_final is None or a._hora_final > limite)
        )
        buckets.append({
            "hora": momento.isoformat(),
            "novos": novos,
            "concluidos": fins,
            "fila": fila,
        })
    return buckets


def _setores(rows, agora, hospital_ids):
    from models.setores import Setores

    setores = Setores.query.filter(Setores.hospital_id.in_(hospital_ids), Setores.ativo.is_(True)).all()
    saida = []
    for s in setores:
        ativos = [a for a in rows if a.setor_id == s.id and a.status in EM_FLUXO]
        em_atend = [a for a in ativos if a.status == STATUS_EM_ATENDIMENTO]
        na_fila = [a for a in ativos if a.status in FILABERTA]
        saida.append({
            "id": s.id,
            "nome": s.nome,
            "sigla": s.sigla,
            "hospital_id": s.hospital_id,
            "em_atendimento": len(em_atend),
            "aguardando": len(na_fila),
            "espera_media_min": _media([_minutos(agora - a._hora_inicio) for a in na_fila]),
        })
    maior = max([s["em_atendimento"] + s["aguardando"] for s in saida], default=0)
    for s in saida:
        s["carga_pct"] = int(round(100 * (s["em_atendimento"] + s["aguardando"]) / maior)) if maior else 0
    return saida


def _tempo_na_fila(rows, agora):
    """Distribuição agregada do tempo decorrido, por faixa e por etapa.

    Substitui a lista individual de pacientes na tela: mostra volume, tempo e
    qualidade sem expor nenhum registro identificável."""
    faixas = [
        ("até 15 min", 0, 15),
        ("15–30 min", 15, 30),
        ("30–60 min", 30, 60),
        ("1–2 h", 60, 120),
        ("2–4 h", 120, 240),
        ("acima de 4 h", 240, None),
    ]
    saida = []
    for rotulo, inicio, fim in faixas:
        contidos = [
            a for a in rows
            if a._hora_inicio and a.status in EM_FLUXO
            and _minutos(agora - a._hora_inicio) >= inicio
            and (fim is None or _minutos(agora - a._hora_inicio) < fim)
        ]
        saida.append({
            "faixa": rotulo,
            "fila": sum(1 for a in contidos if a.status in FILABERTA),
            "em_atendimento": sum(1 for a in contidos if a.status == STATUS_EM_ATENDIMENTO),
        })
    return saida


def _alertas(resumo_base, rows, agora):
    alertas = []
    criticos = [a for a in rows if a.status in FILABERTA and a.prioridade == "alta"]
    if criticos:
        alertas.append({
            "nivel": "critico",
            "titulo": "Fila com prioridade alta",
            "descricao": f"{len(criticos)} atendimento(s) aguardando triagem com prioridade alta.",
        })
    espera = resumo_base["kpis"]["espera_media_min"]
    if espera >= 90:
        alertas.append({
            "nivel": "alto",
            "titulo": "Espera média elevada",
            "descricao": f"A espera média atual é de {espera} minutos.",
        })
    seletiva = [a for a in rows if a._hora_inicio and _minutos(agora - a._hora_inicio) > 240
                and a.status in FILABERTA]
    if seletiva:
        alertas.append({
            "nivel": "alto",
            "titulo": "Pacientes há mais de 4h na fila",
            "descricao": f"{len(seletiva)} atendimento(s) sem movimentação além do limite.",
        })
    sem_triagem = sum(1 for a in rows if a.status == STATUS_AGUARDANDO and a.prioridade == "sem_triagem")
    if sem_triagem:
        alertas.append({
            "nivel": "medio",
            "titulo": "Triagem pendente",
            "descricao": f"{sem_triagem} atendimento(s) aguardando classificação de risco.",
        })
    return alertas


def resumo(hospital_ids, horas=JANELA_HORAS):
    hospital_ids = sorted({int(h) for h in hospital_ids if str(h).isdigit()})
    agora = agora_utc()
    rows = carregar(hospital_ids, horas)

    abertos = [a for a in rows if a.status in EM_FLUXO]
    finalizados = [a for a in rows if a.status == STATUS_FINALIZADO]
    cancelados = [a for a in rows if a.status == STATUS_CANCELADO]
    na_fila = [a for a in rows if a.status in FILABERTA]
    atendendo = [a for a in rows if a.status == STATUS_EM_ATENDIMENTO]
    janela = agora - timedelta(hours=horas)
    atendidos_janela = [a for a in finalizados if a._hora_final and a._hora_final >= janela]

    por_status = {s: sum(1 for a in rows if a.status == s) for s in STATUS}
    por_prioridade = {
        p: {
            "fila": sum(1 for a in na_fila if (a.prioridade or "sem_triagem") == p),
            "em_atendimento": sum(1 for a in atendendo if (a.prioridade or "sem_triagem") == p),
            "atendidos": sum(1 for a in atendidos_janela if (a.prioridade or "sem_triagem") == p),
        }
        for p in PRIORIDADES
    }

    esperas = [_minutos(agora - a._hora_inicio) for a in na_fila]
    permanencias = [_minutos(agora - a._hora_inicio) for a in atendendo]
    duracoes = [_minutos(a._hora_final - a._hora_inicio) for a in atendidos_janela if a._hora_final]

    throughput = len(atendidos_janela)
    projetado = int(round(len(na_fila) * 60 / throughput * horas)) if throughput else None

    saida = {
        "hospitais": hospital_ids,
        "gerado_em": agora.isoformat(),
        "janela_horas": horas,
        "kpis": {
            "aguardando": len(na_fila),
            "em_atendimento": len(atendendo),
            "atendidos_periodo": len(atendidos_janela),
            "cancelados_periodo": len(cancelados),
            "total_abertos": len(abertos),
            "espera_media_min": _media(esperas),
            "espera_max_min": max(esperas) if esperas else 0,
            "permanencia_media_min": _media(permanencias),
            "duracao_media_min": _media(duracoes),
            "tempo_atendido_min": sum(permanencias),
            "tempo_a_atender_min": sum(esperas),
            "projecao_fila_min": projetado,
            "taxa_conclusao": int(round(100 * len(atendidos_janela) / (len(atendidos_janela) + len(cancelados))))
            if (atendidos_janela or cancelados) else None,
        },
        "por_status": por_status,
        "por_prioridade": por_prioridade,
        "filas": _fila(rows, agora),
        "serie": _serie(rows, agora, horas),
        "tempo_na_fila": _tempo_na_fila(rows, agora),
        "setores": _setores(rows, agora, hospital_ids),
        "por_hospital": _por_hospital(rows, agora, hospital_ids),
    }
    saida["alertas"] = _alertas(saida, rows, agora)
    return saida


def _por_hospital(rows, agora, hospital_ids):
    nomes = {h.id: h.nome for h in Hospitais.query.filter(Hospitais.id.in_(hospital_ids)).all()}
    saida = []
    for hid in hospital_ids:
        grupo = [a for a in rows if a.hospital_id == hid]
        saida.append({
            "id": hid,
            "nome": nomes.get(hid, f"Hospital {hid}"),
            "aguardando": sum(1 for a in grupo if a.status in FILABERTA),
            "em_atendimento": sum(1 for a in grupo if a.status == STATUS_EM_ATENDIMENTO),
            "atendidos_24h": sum(1 for a in grupo if a.status == STATUS_FINALIZADO and a._hora_final),
        })
    return saida
