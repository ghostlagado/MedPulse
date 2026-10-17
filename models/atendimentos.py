from models.base_model import BaseModel
from sqlalchemy.sql import func
from utils.db import db

class Atendimentos(BaseModel):
    id = db.Column(db.Integer, primary_key=True)
    hora_inicio = db.Column(db.DateTime(timezone=True), default=func.utcnow)
    hora_final = db.Column(db.DateTime(timezone=True), default=func.utcnow)
    hospital_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("locais.id"), nullable=False)
    status = db.Column(db.String(120))