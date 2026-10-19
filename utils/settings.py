"""Leitura tipada das variáveis de ambiente do MedPulse."""

from os import getenv

from utils.tz import fuso_valido


def bool_env(nome, padrao=False):
    valor = getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in ("1", "true", "yes", "on", "sim")


def int_env(nome, padrao=0):
    try:
        return int(getenv(nome))
    except (TypeError, ValueError):
        return padrao


def float_env(nome, padrao=0.0):
    try:
        return float(getenv(nome))
    except (TypeError, ValueError):
        return padrao


def lista_env(nome, padrao=()):
    valor = getenv(nome)
    if not valor:
        return list(padrao)
    return [item.strip() for item in valor.split(",") if item.strip()]


def carregar(app):
    """Aplica as configurações do ambiente no app Flask."""
    app.config["SHOWCASE_ENABLED"] = bool_env("SHOWCASE_ENABLED", False)
    app.config["SHOWCASE_INTERVALO_MS"] = int_env("SHOWCASE_INTERVALO_MS", 2600)
    app.config["SHOWCASE_VELOCIDADE"] = float_env("SHOWCASE_VELOCIDADE", 6.0)
    app.config["SHOWCASE_MAX_ABERTOS"] = int_env("SHOWCASE_MAX_ABERTOS", 140)
    app.config["SHOWCASE_HOSPITAIS"] = [
        int(i) for i in lista_env("SHOWCASE_HOSPITAIS") if i.isdigit()
    ]
    app.config["SHOWCASE_LOCAIS"] = lista_env("SHOWCASE_LOCAIS")
    app.config["WEBHOOK_TOKEN"] = getenv("WEBHOOK_TOKEN") or None
    # Fuso da operação hospitalar: única referência temporal do relógio do painel.
    fuso = getenv("TIMEZONE") or "America/Sao_Paulo"
    if not fuso_valido(fuso):
        fuso = "America/Sao_Paulo"
    app.config["FUSO_HORARIO"] = fuso
    return app.config
