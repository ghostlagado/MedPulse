"""Showcase sintético do MedPulse.

Gera movimento contínuo e plausível **somente** em hospitais marcados com
`demo=True`, exercitando o mesmo caminho de escrita do webhook (validação,
máquina de estados, persistência e emissão Socket.IO). Nenhum dado sintético é
escrito em hospitais reais.
"""

import logging
import math
import os
import random
import threading
import uuid
from datetime import timedelta

from utils.db import db
from utils.tz import agora_utc, para_utc
from models.atendimentos import (
    Atendimentos,
    PRIORIDADE_ALTA,
    PRIORIDADE_BAIXA,
    PRIORIDADE_INTERMEDIARIA,
    PRIORIDADE_NAO_URGENTE,
    PRIORIDADE_SEM_TRIAGEM,
    STATUS_AGUARDANDO,
    STATUS_CANCELADO,
    STATUS_EM_ATENDIMENTO,
    STATUS_FINALIZADO,
    STATUS_TRIAGEM,
)
from models.hospitais import Hospitais
from models.locais import Locais
from models.setores import Setores
from services import atendimentos as svc

log = logging.getLogger("medpulse.showcase")

NOME_DEMO = "UBA Londres - Demonstração"

SETORES_DEMO = [
    ("Recepção", "REC"),
    ("Triagem", "TRI"),
    ("Emergência Adulto", "ERA"),
    ("Sala Vermelha", "SVER"),
    ("Sala Amarela", "SAMA"),
    ("Consultório 1", "CON1"),
    ("Consultório 2", "CON2"),
    ("Observação", "OBS"),
    ("Diagnóstico por Imagem", "DPI"),
    ("Farmácia", "FAR"),
]

# Nomes exclusivamente fictícios, sem qualquer vínculo com pacientes reais.
NOMES = [
    "Ana", "Bruno", "Carla", "Diego", "Elisa", "Felipe", "Gabriela", "Heitor",
    "Isadora", "João", "Karina", "Lucas", "Mariana", "Nelson", "Olívia", "Paulo",
    "Quésia", "Rafael", "Sofia", "Thiago", "Ursula", "Vinícius", "Wesley", "Yara",
    "Zilda", "Áureo", "Bento", "Célia", "Davi", "Emanuel",
]
SOBRENOMES = [
    "Almeida", "Barros", "Cardoso", "Duarte", "Esteves", "Ferreira", "Gomes",
    "Horta", "Iglesias", "Jesus", "Klein", "Lima", "Moraes", "Nogueira", "Oliveira",
    "Pacheco", "Queiroz", "Ramos", "Silveira", "Teixeira", "Unno", "Vasques",
]

# Curva de chegada por hora (0-23): manhãs e início da noite concentram o fluxo.
CURVA_DIURNA = [
    0.25, 0.18, 0.14, 0.12, 0.14, 0.25, 0.55, 0.95, 1.25, 1.35,
    1.25, 1.10, 0.95, 0.90, 1.00, 1.10, 1.25, 1.35, 1.20, 1.00,
    0.80, 0.60, 0.45, 0.32,
]
FLUXO_BASE_POR_HORA = 9.0  # chegadas/hora na curva-base do hospital demonstrativo

PESO_PRIORIDADE = [
    (PRIORIDADE_ALTA, 7),
    (PRIORIDADE_INTERMEDIARIA, 20),
    (PRIORIDADE_BAIXA, 33),
    (PRIORIDADE_NAO_URGENTE, 28),
    (PRIORIDADE_SEM_TRIAGEM, 12),
]

# Tempo médio de permanência por prioridade, em minutos (triagem, atendimento).
TAU = {
    STATUS_AGUARDANDO: {
        PRIORIDADE_ALTA: 3, PRIORIDADE_INTERMEDIARIA: 9, PRIORIDADE_BAIXA: 18,
        PRIORIDADE_NAO_URGENTE: 28, PRIORIDADE_SEM_TRIAGEM: 6,
    },
    STATUS_TRIAGEM: {
        PRIORIDADE_ALTA: 3, PRIORIDADE_INTERMEDIARIA: 4, PRIORIDADE_BAIXA: 5,
        PRIORIDADE_NAO_URGENTE: 6, PRIORIDADE_SEM_TRIAGEM: 5,
    },
    STATUS_EM_ATENDIMENTO: {
        PRIORIDADE_ALTA: 48, PRIORIDADE_INTERMEDIARIA: 38, PRIORIDADE_BAIXA: 26,
        PRIORIDADE_NAO_URGENTE: 18, PRIORIDADE_SEM_TRIAGEM: 20,
    },
}

DESTINOS_EM_ATENDIMENTO = {
    PRIORIDADE_ALTA: ["Sala Vermelha", "Emergência Adulto"],
    PRIORIDADE_INTERMEDIARIA: ["Sala Amarela", "Observação", "Consultório 1"],
    PRIORIDADE_BAIXA: ["Consultório 1", "Consultório 2", "Observação"],
    PRIORIDADE_NAO_URGENTE: ["Consultório 1", "Consultório 2"],
    PRIORIDADE_SEM_TRIAGEM: ["Triagem", "Recepção"],
}
APOIO = ["Diagnóstico por Imagem", "Farmácia", "Observação"]

ABERTOS = (STATUS_AGUARDANDO, STATUS_TRIAGEM, STATUS_EM_ATENDIMENTO)


class ShowcaseIsolamento(RuntimeError):
    """Bloqueia escrita de dados sintéticos fora do ambiente demonstrativo."""


def alvos(app):
    """Hospitais autorizados a receber dados sintéticos."""
    consulta = Hospitais.query.filter(Hospitais.ativo.is_(True), Hospitais.demo.is_(True))
    ids = app.config.get("SHOWCASE_HOSPITAIS") or []
    if ids:
        consulta = consulta.filter(Hospitais.id.in_(ids))
    return consulta.all()


def _sortear_prioridade(rng):
    total = sum(p for _, p in PESO_PRIORIDADE)
    escolha = rng.uniform(0, total)
    acumulado = 0
    for nome, peso in PESO_PRIORIDADE:
        acumulado += peso
        if escolha <= acumulado:
            return nome
    return PRIORIDADE_BAIXA


def _nome_ficticio(rng):
    return f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}"


def _poisson(lam, rng):
    if lam <= 0:
        return 0
    limite, k, p = math.exp(-lam), 0, 1.0
    while k < 30:
        k += 1
        p *= rng.random()
        if p <= limite:
            return k - 1
    return k


def _p(dt, tau):
    """Probabilidade de transição no intervalo dt, com média exponencial tau."""
    return 1 - math.exp(-max(dt, 0.01) / max(tau, 0.1))


def _setor_por_nome(hospital, nome):
    for s in hospital.setores:
        if s.ativo and s.nome == nome:
            return s.id
    return None


def _payload(atendimento, **mudancas):
    dados = {
        "protocolo": atendimento.protocolo,
        "hospital_id": atendimento.hospital_id,
        "paciente": atendimento.paciente,
        "prioridade": atendimento.prioridade,
        "status": atendimento.status,
    }
    if atendimento.setor_id:
        dados["setor_id"] = atendimento.setor_id
    dados.update(mudancas)
    return dados


def gerar_chegadas(hospital, dt_min, agora, rng, limite_restante, vel=1.0):
    """Cria novos atendimentos no hospital demonstrativo."""
    fator = CURVA_DIURNA[agora.hour % 24]
    pico_extra = 3.0 if rng.random() < 0.02 else 1.0
    lam = FLUXO_BASE_POR_HORA * fator * pico_extra * vel * dt_min / 60.0
    quantidade = min(_poisson(lam, rng), limite_restante)
    criados = []
    for _ in range(quantidade):
        protocolo = f"DEMO-{hospital.id}-{uuid.uuid4().hex[:10]}"
        inicio = agora - timedelta(minutes=rng.uniform(0, min(dt_min, 4)))
        registro, acao = svc.registrar({
            "protocolo": protocolo,
            "hospital_id": hospital.id,
            "status": STATUS_AGUARDANDO,
            "prioridade": _sortear_prioridade(rng),
            "paciente": _nome_ficticio(rng),
            "setor_id": _setor_por_nome(hospital, "Recepção"),
            "hora_inicio": inicio.isoformat(),
            "atualizado_em": inicio.isoformat(),
        }, fonte="showcase")
        if acao == "criado":
            criados.append(registro)
    return criados


def progressir(hospital, dt_min, agora, rng, vel=1.0):
    """Avança a fila: triagem, início/conclusão de atendimento e movimentações."""
    abertos = (
        Atendimentos.query
        .filter(Atendimentos.hospital_id == hospital.id, Atendimentos.status.in_(ABERTOS))
        .order_by(Atendimentos.id)
        .all()
    )
    mudancas = []
    for atendimento in abertos:
        inicio = para_utc(atendimento.hora_inicio) or agora
        idade = (agora - inicio).total_seconds() / 60.0
        if idade < 1.0:
            continue
        prioridade = atendimento.prioridade or PRIORIDADE_SEM_TRIAGEM
        # Ruído estável por protocolo+estado: define o tempo esperado da etapa, para
        # que pacientes da mesma prioridade não evoluam todos no mesmo ciclo.
        ruído = random.Random(f"{atendimento.protocolo}:{atendimento.status}")
        tau = TAU.get(atendimento.status, {}).get(prioridade, 20) * ruído.uniform(0.7, 1.5) / vel
        if idade < tau * 0.30:  # tempo mínimo de etapa antes de qualquer movimento
            continue
        dt = dt_min * ruído.uniform(0.7, 1.4)
        # As decisões usam o rng do ciclo: um rng fixo por estado repetiria o mesmo
        # sorteio em todos os ciclos e a fila congelaria.
        mudanca = _decidir_transicao(atendimento, hospital, prioridade, dt, agora, rng, tau)
        if mudanca:
            _, acao = svc.registrar(_payload(atendimento, **mudanca), fonte="showcase")
            if acao != "ignorada":
                mudancas.append(atendimento)
    return mudancas


def _decidir_transicao(atendimento, hospital, prioridade, dt, agora, rng, tau):
    status = atendimento.status
    if status == STATUS_AGUARDANDO:
        if rng.random() < 0.006 * dt:  # desistência / não comparecimento
            return {"status": STATUS_CANCELADO, "hora_final": agora.isoformat()}
        if rng.random() < _p(dt, tau):
            destino = {"status": STATUS_TRIAGEM, "setor_id": _setor_por_nome(hospital, "Triagem")}
            if atendimento.prioridade == PRIORIDADE_SEM_TRIAGEM:
                destino["prioridade"] = _sortear_prioridade(rng)
            return destino
        return None

    if status == STATUS_TRIAGEM:
        if rng.random() < _p(dt, tau):
            opcoes = DESTINOS_EM_ATENDIMENTO.get(prioridade, ["Observação"])
            return {
                "status": STATUS_EM_ATENDIMENTO,
                "setor_id": _setor_por_nome(hospital, rng.choice(opcoes)),
            }
        return None

    if status == STATUS_EM_ATENDIMENTO:
        if rng.random() < _p(dt, tau):
            return {"status": STATUS_FINALIZADO, "hora_final": agora.isoformat(),
                    "setor_id": _setor_por_nome(hospital, "Farmácia")}
        if rng.random() < 0.015 * dt:  # retorno à fila (ex.: vaga indisponível)
            return {"status": STATUS_AGUARDANDO, "setor_id": _setor_por_nome(hospital, "Recepção")}
        if rng.random() < 0.04 * dt:  # deslocamento interno para exame/observação
            return {"setor_id": _setor_por_nome(hospital, rng.choice(APOIO))}
        return None

    return None


def passo(app, agora=None, rng=None, registrar_log=True, dt_min=None, velocidade=None):
    """Executa um ciclo completo do gerador para todos os hospitais demo."""
    agora = agora or agora_utc()
    rng = rng or random.Random()
    vel = max(float(velocidade if velocidade is not None
                    else app.config.get("SHOWCASE_VELOCIDADE", 6.0) or 6.0), 0.05)
    if dt_min is None:
        # Minutos reais decorridos desde o último ciclo: as taxas de transição são
        # calibradas em minutos, então acelerar a demo muda as taxas, não o relógio.
        global _ultimo_ciclo
        dt_min = 0.0 if _ultimo_ciclo is None else (agora - _ultimo_ciclo).total_seconds() / 60.0
        _ultimo_ciclo = agora
        if dt_min <= 0:
            dt_min = max(int(app.config.get("SHOWCASE_INTERVALO_MS", 2600)), 250) / 60000.0
        dt_min = min(max(dt_min, 0.02), 10.0)

    total = 0
    for hospital in alvos(app):
        if not hospital.demo:
            raise ShowcaseIsolamento(f"hospital {hospital.id} não é ambiente de demonstração")
        limite = int(app.config.get("SHOWCASE_MAX_ABERTOS", 140))
        abertos = Atendimentos.query.filter(
            Atendimentos.hospital_id == hospital.id,
            Atendimentos.status.in_(ABERTOS),
        ).count()
        novos = gerar_chegadas(hospital, dt_min, agora, rng, max(limite - abertos, 0), vel)
        mudados = progressir(hospital, dt_min, agora, rng, vel)
        total += len(novos) + len(mudados)
        if registrar_log and (novos or mudados):
            log.info("showcase %s: +%d novos, %d atualizados", hospital.nome, len(novos), len(mudados))
    return total


def semear_backlog(app, minutos=210, rng=None):
    """Preenche a fila inicial para que o painel não nasça vazio."""
    rng = rng or random.Random()
    agora = agora_utc()
    criados = 0
    for hospital in alvos(app):
        if not hospital.demo:
            raise ShowcaseIsolamento(f"hospital {hospital.id} não é ambiente de demonstração")
        for _ in range(int(minutos / 9)):
            inicio = agora - timedelta(minutes=rng.uniform(2, minutos))
            prioridade = _sortear_prioridade(rng)
            idade = (agora - inicio).total_seconds() / 60.0
            tau_atendimento = TAU[STATUS_EM_ATENDIMENTO][prioridade]
            sorteio = rng.random()
            if idade > tau_atendimento * 2.2 and sorteio < 0.82:
                status, fim = STATUS_FINALIZADO, inicio + timedelta(
                    minutes=min(idade, rng.uniform(tau_atendimento * 0.7, tau_atendimento * 1.9)))
            elif idade > tau_atendimento:
                status, fim = STATUS_EM_ATENDIMENTO, None
            elif idade > 25:
                status, fim = STATUS_TRIAGEM, None
            else:
                status, fim = STATUS_AGUARDANDO, None
            destino = DESTINOS_EM_ATENDIMENTO.get(prioridade, ["Observação"])
            setor = "Recepção" if status == STATUS_AGUARDANDO else (
                "Triagem" if status == STATUS_TRIAGEM else rng.choice(destino))
            _, acao = svc.registrar({
                "protocolo": f"DEMO-{hospital.id}-{uuid.uuid4().hex[:10]}",
                "hospital_id": hospital.id,
                "status": status,
                "prioridade": prioridade,
                "paciente": _nome_ficticio(rng),
                "setor_id": _setor_por_nome(hospital, setor),
                "hora_inicio": inicio.isoformat(),
                "hora_final": fim.isoformat() if fim else None,
                "atualizado_em": (fim or inicio).isoformat(),
            }, fonte="showcase")
            criados += acao == "criado"
    return criados


def preparar_demo(app, local_nome=None):
    """Cria/atualiza o hospital demonstrativo e seus setores (idempotente)."""
    if local_nome:
        local = Locais.query.filter(db.func.lower(Locais.nome) == local_nome.lower()).first()
    else:
        local = Locais.query.order_by(Locais.id).first()
    if not local:
        raise RuntimeError("nenhum local cadastrado; crie o local antes do showcase")

    hospital = Hospitais.query.filter_by(local_id=local.id, nome=NOME_DEMO).first()
    if not hospital:
        hospital = Hospitais(nome=NOME_DEMO, local_id=local.id, ativo=True, demo=True)
        db.session.add(hospital)
        db.session.flush()
    else:
        hospital.demo = True

    existentes = {s.nome for s in Setores.query.filter_by(hospital_id=hospital.id).all()}
    for nome, sigla in SETORES_DEMO:
        if nome not in existentes:
            db.session.add(Setores(nome=nome, sigla=sigla, hospital_id=hospital.id, ativo=True))
    db.session.commit()
    return hospital


def _loop(app, parada, rng=None):
    rng = rng or random.Random()
    base_ms = max(int(app.config.get("SHOWCASE_INTERVALO_MS", 2600)), 250)
    while not parada.is_set():
        # Intervalo variado de propósito: ciclos idênticos entregariam rajadas
        # reconhecíveis na série temporal do painel.
        espera = base_ms * rng.uniform(0.55, 1.9) / 1000.0
        if parada.wait(espera):
            break
        try:
            with app.app_context():
                passo(app, rng=rng)
        except Exception:
            log.exception("falha no ciclo do showcase")


_thread = None
_parada = threading.Event()
_ultimo_ciclo = None


def iniciar(app):
    """Liga o gerador em background quando SHOWCASE_ENABLED=true."""
    global _thread, _parada
    if not app.config.get("SHOWCASE_ENABLED"):
        return None
    # O reloader do Werkzeug importa o módulo duas vezes: só o processo filho gera dados.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return None
    if _thread and _thread.is_alive():
        return _thread
    with app.app_context():
        alvos_app = alvos(app)
    if not alvos_app:
        log.warning("showcase habilitado, mas nenhum hospital com demo=True existe")
        return None
    _parada = threading.Event()
    _thread = threading.Thread(target=_loop, args=(app, _parada), name="medpulse-showcase", daemon=True)
    _thread.start()
    log.info("showcase ativo em: %s", ", ".join(h.nome for h in alvos_app))
    return _thread


def parar():
    _parada.set()
