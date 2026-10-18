from models.base_model import BaseModel
from datetime import datetime
from utils.db import db

class Atendimentos(BaseModel):
    id = db.Column(db.Integer, primary_key=True)
    hora_inicio = db.Column(db.DateTime, timezone=True, default=datetime.now())
    hora_final = db.Column(db.DateTime, timezone=True, default=datetime.now())
    status = db.Column(db.DateTime, timezone=True)