from models.base_model import BaseModel
from utils.db import db

class Locais(BaseModel):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String)
    ativo = db.Column(db.Boolean, default=True)