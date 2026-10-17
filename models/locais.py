from models.base_model import BaseModel
from utils.db import db
import uuid

class Locais(BaseModel):
    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = db.Column(db.String)
    ativo = db.Column(db.Boolean, default=True)
    
    hospitais = db.relationship('Hospitais', backref='hospitais', lazy=True)