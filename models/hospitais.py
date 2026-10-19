from models.base_model import BaseModel
from utils.db import db


class Hospitais(BaseModel):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    local_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("locais.id"), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    # Ambiente demonstrativo: único alvo permitido para dados sintéticos do showcase.
    demo = db.Column(db.Boolean, default=False, nullable=False)

    setores = db.relationship("Setores", backref="hospitais", lazy=True)
