from models.base_model import BaseModel
from utils.db import db
import uuid

class Hospitais(BaseModel):
    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = db.Column(db.String(100), nullable=False)
    local_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("locais.id"), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)