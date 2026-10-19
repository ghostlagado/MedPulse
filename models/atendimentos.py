from models.base_model import BaseModel
from sqlalchemy.sql import func
from utils.db import db


# Única fonte de verdade para os rótulos de fluxo usados pela API, pelo
# showcase sintético e pelo frontend (via /api/config).
STATUS_AGUARDANDO = "aguardando"
STATUS_TRIAGEM = "triagem"
STATUS_EM_ATENDIMENTO = "em_atendimento"
STATUS_FINALIZADO = "finalizado"
STATUS_CANCELADO = "cancelado"

STATUS = (
    STATUS_AGUARDANDO,
    STATUS_TRIAGEM,
    STATUS_EM_ATENDIMENTO,
    STATUS_FINALIZADO,
    STATUS_CANCELADO,
)

# Transições válidas. Estados finais não evoluem mais.
TRANSICOES = {
    STATUS_AGUARDANDO: {STATUS_TRIAGEM, STATUS_EM_ATENDIMENTO, STATUS_CANCELADO},
    STATUS_TRIAGEM: {STATUS_AGUARDANDO, STATUS_EM_ATENDIMENTO, STATUS_CANCELADO},
    STATUS_EM_ATENDIMENTO: {STATUS_AGUARDANDO, STATUS_FINALIZADO, STATUS_CANCELADO},
    STATUS_FINALIZADO: set(),
    STATUS_CANCELADO: set(),
}

ESTADOS_FINAIS = frozenset(k for k, v in TRANSICOES.items() if not v)

PRIORIDADE_ALTA = "alta"
PRIORIDADE_INTERMEDIARIA = "intermediaria"
PRIORIDADE_BAIXA = "baixa"
PRIORIDADE_NAO_URGENTE = "nao_urgente"
PRIORIDADE_SEM_TRIAGEM = "sem_triagem"

PRIORIDADES = (
    PRIORIDADE_ALTA,
    PRIORIDADE_INTERMEDIARIA,
    PRIORIDADE_BAIXA,
    PRIORIDADE_NAO_URGENTE,
    PRIORIDADE_SEM_TRIAGEM,
)


class Atendimentos(BaseModel):
    id = db.Column(db.Integer, primary_key=True)

    hora_inicio = db.Column(db.DateTime(timezone=True), default=func.now())
    hora_final = db.Column(db.DateTime(timezone=True))

    status = db.Column(db.String(120), default=STATUS_AGUARDANDO, nullable=False)

    hospital_id = db.Column(
        db.Integer,
        db.ForeignKey("hospitais.id"),
        nullable=False
    )
    setor_id = db.Column(
        db.Integer,
        db.ForeignKey("setores.id"),
        nullable=True
    )

    # Chave de idempotência enviada pelo sistema de origem no webhook.
    protocolo = db.Column(db.String(64), unique=True)
    # Rótulo de exibição do paciente: sempre um apelido/identificador, nunca dado clínico real.
    paciente = db.Column(db.String(120))
    prioridade = db.Column(db.String(20), default=PRIORIDADE_SEM_TRIAGEM, nullable=False)

    # Usada para descartar atualizações fora de ordem vindas do webhook.
    atualizado_em = db.Column(
        db.DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    hospital = db.relationship("Hospitais", lazy="joined")
    setor = db.relationship("Setores", lazy="joined")
