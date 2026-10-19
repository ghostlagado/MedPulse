from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones


def agora_utc():
    return datetime.now(timezone.utc)


def zona(nome):
    """Resolve o fuso configurado para a operação; se o nome for inválido, usa UTC."""
    try:
        return ZoneInfo(nome)
    except Exception:
        return timezone.utc


def agora_local(nome):
    return agora_utc().astimezone(zona(nome))


def para_utc(valor):
    """Normaliza datas vindas do banco (timestamptz) ou do JSON (naive ISO)."""
    if valor is None:
        return None
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


def para_local(valor, nome):
    utc = para_utc(valor)
    return utc.astimezone(zona(nome)) if utc else None


def fuso_valido(nome):
    return nome in available_timezones()
