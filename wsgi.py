"""Ponto de entrada WSGI para produção: `gunicorn wsgi:app`.

O `app.py` é o runner local (sobe o servidor de desenvolvimento com Socket.IO).
Aqui apenas expomos a aplicação para um servidor WSGI real.
"""

from app import app  # noqa: F401
