from models.base_model import BaseModel
from sqlalchemy.sql import func
from utils.db import db
import uuid


class Locais(BaseModel):
    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                   server_default=func.gen_random_uuid())
    nome = db.Column(db.String)
    ativo = db.Column(db.Boolean, default=True)

    hospitais = db.relationship('Hospitais', backref='hospitais', lazy=True)
