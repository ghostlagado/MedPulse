from flask_migrate import Migrate
from utils.blueprints import bps
from dotenv import load_dotenv
from flask_cors import CORS
from flask import Flask
from os import getenv
import importlib
import pkgutil
import models
from utils import (
    db, socket
)


load_dotenv() # Carrega .env

# Vairveis de configuração
DEBUG = getenv("DEBUG")
HOST = getenv("HOST")
PORT = getenv("PORT")
PEPPER = getenv("PEPPER")
DB_URI = getenv("DB_URI")
SECRET = getenv("SECRET")

# Cria o APP
app = Flask(__name__)
CORS(app, cors_allowed_origins="*")

# COnfig basica do APP
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
app.config["SECRET_KEY"] = SECRET
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# Inicia o Banco de Dados
db.db.init_app(app)

# Resposavel por importar todos os Models automaticamente, mesmo que ainda nao instanciado
def importar_models_automaticamente(package):
    """Importa recursivamente todos os submódulos de um pacote."""
    
    for _, module_name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        importlib.import_module(module_name)
        if is_pkg:
            # Se for uma subpasta com mais models dentro, varre ela também
            importar_models_automaticamente(importlib.import_module(module_name))

# Executa o import de todos os arquivos dentro da pasta models
importar_models_automaticamente(models)

# Agora sim o Migrate vai enxergar tudo perfeitamente!
migrate = Migrate(app, db.db)

# Faz os migrations usando Alembic
migrate = Migrate(app, db.db) 

# Inicia o WebSocket
socket.socket.init_app(app)

# Registra os Blueprints    
for bp in bps: app.register_blueprint(bp, url_prefix=bps[bp])

if __name__ == '__main__':
    socket.socket.run( app, host=HOST, port=PORT, debug=DEBUG )