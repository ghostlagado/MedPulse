"""Rotas de página: entregam o shell do painel; os dados chegam pela API/Socket.IO."""

from flask import Blueprint, abort, current_app, render_template

from utils.db import db, uuid_de
from models.locais import Locais

main_bp = Blueprint("Rota Principal", __name__)


def _render(local):
    hospitais = [h for h in local.hospitais if h.ativo]
    return render_template(
        "index.html",
        local=local,
        hospitais=hospitais,
        hospitais_info=[{"id": h.id, "nome": h.nome, "demo": bool(h.demo)} for h in hospitais],
        local_token=str(local.id),
        showcase_ativo=bool(current_app.config.get("SHOWCASE_ENABLED")),
    )


def _primeiro_local():
    return (
        Locais.query.filter_by(ativo=True).order_by(Locais.nome.asc()).first()
        or Locais.query.order_by(Locais.id).first()
    )


@main_bp.route("/", methods=["GET"])
def inicio():
    local = _primeiro_local()
    if not local:
        return render_template(
            "erro.html",
            titulo="Nenhum local cadastrado",
            mensagem="Cadastre um local e seus hospitais, ou rode `flask demo init` "
                     "para criar o ambiente de demonstração.",
        ), 404
    return _render(local)


@main_bp.route("/<uuid:local_token>", methods=["GET"])
def painel(local_token):
    local = db.session.get(Locais, uuid_de(local_token))
    if not local:
        abort(404)
    return _render(local)
