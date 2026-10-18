from dotenv import load_dotenv
from flask_cors import CORS
from flask import Flask
from os import getenv
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

# Cria o APP
app = Flask(__name__)
CORS(app, cors_allowed_origins="*")

# COnfig basica do APP
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Inicia o Banco de Dados
db.db.init_app(app)

# Inicia o WebSocket
socket.socket.init_app(app)

if __name__ == '__main__':
    socket.socket.run( app, host=HOST, port=PORT, debug=DEBUG )