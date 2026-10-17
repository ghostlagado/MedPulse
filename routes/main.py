from flask import render_template, Blueprint
from models.locais import Locais

main_bp = Blueprint("Rota Principal", __name__)

@main_bp.route("/<uuid:local_token>", methods=["GET"])
def index(local_token):
    local = Locais.query.get_or_404(local_token)
    hospitais = local.hospitais
    
    return render_template(
        "index.html", 
        local=local, 
        hospitais=hospitais
    )