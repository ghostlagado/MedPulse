from models.base_model import BaseModel
from utils.db import db


class Setores(BaseModel):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    sigla = db.Column(db.String(10))
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitais.id"), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
