from utils.db import db
import datetime
import uuid


class BaseModel(db.Model):
    __abstract__ = True

    def to_dict(self):
        dados = {}
        for c in self.__table__.columns:
            valor = getattr(self, c.name)
            if isinstance(valor, (datetime.datetime, datetime.date)):
                valor = valor.isoformat()
            elif isinstance(valor, uuid.UUID):
                valor = str(valor)
            dados[c.name] = valor
        return dados
