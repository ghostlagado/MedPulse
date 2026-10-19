from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv

import importlib
import pkgutil
from os import getenv

import models
from utils import db, settings, socket
from utils.blueprints import bps

load_dotenv()  # Carrega .env

DEBUG = settings.bool_env("DEBUG", False)
HOST = getenv("HOST", "127.0.0.1")
PORT = settings.int_env("PORT", 5000)
DB_URI = getenv("DB_URI")
SECRET = getenv("SECRET")

app = Flask(__name__)
CORS(app, cors_allowed_origins="*")

app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
app.config["SECRET_KEY"] = SECRET or "dev-secret-informe-no-env"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
settings.carregar(app)


def importar_models_automaticamente(package):
    """Importa recursivamente todos os submódulos de um pacote."""
    for _, module_name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        importlib.import_module(module_name)
        if is_pkg:
            importar_models_automaticamente(importlib.import_module(module_name))


importar_models_automaticamente(models)

db.db.init_app(app)
migrate = Migrate(app, db.db)
socket.socket.init_app(app)

for bp in bps:
    app.register_blueprint(bp, url_prefix=bps[bp])

# Handlers Socket.IO + gerador sintético do showcase
from cli import registrar_cli            # noqa: E402
from services import realtime            # noqa: E402
from services import showcase            # noqa: E402

realtime.registrar_handlers(app)
registrar_cli(app)
showcase.iniciar(app)


@app.errorhandler(404)
def nao_encontrado(erro):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "erro": "recurso não encontrado", "codigo": "nao_encontrado"}), 404
    return render_template("erro.html", titulo="Página não encontrada",
                           mensagem="Verifique o endereço do painel ou o token do local."), 404


@app.errorhandler(500)
def erro_interno(erro):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "erro": "erro interno", "codigo": "erro_interno"}), 500
    return render_template("erro.html", titulo="Erro interno",
                           mensagem="Tente novamente em instantes."), 500


@app.teardown_appcontext
def encerrar_workers(excecao):
    if excecao is not None:
        db.db.session.rollback()


if __name__ == '__main__':
    # Runner local. Em produção o entry point é wsgi.py servido por um WSGI server.
    socket.socket.run(app, host=HOST, port=PORT, debug=DEBUG, allow_unsafe_werkzeug=not DEBUG)
