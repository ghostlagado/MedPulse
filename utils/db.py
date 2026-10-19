import uuid

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def uuid_de(valor):
    """Converte o token vindo da URL em UUID (as_uuid=True exige o objeto)."""
    if isinstance(valor, uuid.UUID):
        return valor
    return uuid.UUID(str(valor))
