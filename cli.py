"""Comandos de administração do MedPulse (`flask demo ...`)."""

import random

import click

from utils.db import db
from models.atendimentos import Atendimentos
from models.hospitais import Hospitais
from models.locais import Locais
from services import showcase


@click.group("demo")
def demo_grupo():
    """Administra o ambiente demonstrativo (showcase sintético)."""


def registrar_cli(app):
    @demo_grupo.command("listar")
    def listar():
        with app.app_context():
            for local in Locais.query.all():
                click.secho(f"Local {local.id} - {local.nome}", fg="cyan")
                for h in local.hospitais:
                    marca = " (DEMO)" if h.demo else ""
                    click.echo(f"  hospital {h.id}: {h.nome}{marca} ativo={h.ativo}")

    @demo_grupo.command("init")
    @click.option("--local", "local_nome", default=None, help="Nome do local que recebe o hospital demo.")
    @click.option("--backlog", "minutos", default=0, type=int,
                  help="Preenche a fila simulando os últimos N minutos.")
    def init(local_nome, minutos):
        with app.app_context():
            hospital = showcase.preparar_demo(app, local_nome)
            click.secho(f"Hospital demonstrativo pronto: {hospital.nome} (id {hospital.id})", fg="green")
            if minutos:
                total = showcase.semear_backlog(app, minutos=minutos)
                click.secho(f"{total} atendimentos sintéticos semeados.", fg="green")

    @demo_grupo.command("tick")
    @click.option("--ciclos", default=10, show_default=True, type=int, help="Ciclos a executar.")
    @click.option("--dt", "minutos", default=None, type=float, help="Minutos reais por ciclo.")
    @click.option("--velocidade", default=None, type=float, help="Acelera taxas de chegada e de transição.")
    @click.option("--semente", default=None, type=int, help="Semente do gerador (reprodutível).")
    def tick(ciclos, minutos, velocidade, semente):
        with app.app_context():
            rng = random.Random(semente) if semente is not None else random.Random()
            total = 0
            for _ in range(ciclos):
                total += showcase.passo(app, rng=rng, dt_min=minutos,
                                        velocidade=velocidade, registrar_log=False)
            click.secho(f"{total} mudanças aplicadas em {ciclos} ciclo(s).", fg="green")

    @demo_grupo.command("limpar")
    @click.option("--hospital", "hospital_id", required=True, type=int)
    @click.option("--confirmar", is_flag=True, help="Sem esta flag nada é apagado.")
    def limpar(hospital_id, confirmar):
        with app.app_context():
            hospital = db.session.get(Hospitais, hospital_id)
            if not hospital:
                raise click.ClickException("hospital inexistente")
            if not hospital.demo:
                raise click.ClickException("recusado: hospital não é ambiente de demonstração")
            consulta = Atendimentos.query.filter(
                Atendimentos.hospital_id == hospital.id,
                Atendimentos.protocolo.like("DEMO-%"),
            )
            quantidade = consulta.count()
            if not confirmar:
                click.secho(f"Dry-run: {quantidade} atendimentos sintéticos seriam removidos.", fg="yellow")
                return
            consulta.delete(synchronize_session=False)
            db.session.commit()
            click.secho(f"{quantidade} atendimentos sintéticos removidos.", fg="red")

    app.cli.add_command(demo_grupo)
