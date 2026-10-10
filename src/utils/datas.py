from datetime import date

MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def intervalo_do_mes(mes: str) -> tuple[date, date]:
    """'2026-03' -> (2026-03-01, 2026-04-01): início inclusivo, fim exclusivo."""
    ano, numero = map(int, mes.split("-"))
    inicio = date(ano, numero, 1)
    fim = date(ano + 1, 1, 1) if numero == 12 else date(ano, numero + 1, 1)
    return inicio, fim


def rotulo_mes(mes: str) -> str:
    """'2026-10' -> 'out/2026'."""
    ano, numero = mes.split("-")
    return f"{MESES_ABREV[int(numero) - 1]}/{ano}"


def deslocar_meses(d: date, n: int) -> date:
    """Primeiro dia do mês de `d`, deslocado em n meses (n pode ser negativo)."""
    indice = d.year * 12 + (d.month - 1) + n
    return date(indice // 12, indice % 12 + 1, 1)


def intervalo_do_trimestre(ano: int, trimestre: int) -> tuple[date, date]:
    inicio = date(ano, (trimestre - 1) * 3 + 1, 1)
    return inicio, deslocar_meses(inicio, 3)


def intervalo_do_ano(ano: int) -> tuple[date, date]:
    return date(ano, 1, 1), date(ano + 1, 1, 1)


def periodo_anterior(inicio: date, fim: date, meses: int | None = None) -> tuple[date, date]:
    """Período imediatamente anterior, de mesma duração.

    Para períodos fechados em meses (1, 3 ou 12), informe `meses`; sem ele,
    o período anterior tem o mesmo número de dias.
    """
    if meses:
        return deslocar_meses(inicio, -meses), inicio
    return inicio - (fim - inicio), inicio