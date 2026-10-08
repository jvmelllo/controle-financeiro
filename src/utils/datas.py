from datetime import date


def intervalo_do_mes(mes: str) -> tuple[date, date]:
    """'2026-03' -> (2026-03-01, 2026-04-01): início inclusivo, fim exclusivo."""
    ano, numero = map(int, mes.split("-"))
    inicio = date(ano, numero, 1)
    fim = date(ano + 1, 1, 1) if numero == 12 else date(ano, numero + 1, 1)
    return inicio, fim