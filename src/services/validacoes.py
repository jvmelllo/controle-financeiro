from datetime import date

LIMITE_VALOR = 100_000_000  # R$ 1.000.000,00 em centavos


def validar_lancamento(data: date, centavos: int, hoje: date | None = None) -> tuple[list[str], list[str]]:
    """Devolve (erros, avisos). Erros impedem o salvamento; avisos só alertam."""
    hoje = hoje or date.today()
    erros: list[str] = []
    avisos: list[str] = []

    if centavos <= 0:
        erros.append("Informe um valor maior que zero.")
    elif centavos > LIMITE_VALOR:
        erros.append("O valor parece alto demais (limite de R$ 1.000.000,00). Confira se digitou certo.")

    if data.year < 2000:
        erros.append("Data inválida.")
    elif data > hoje:
        avisos.append("A data está no futuro. Confira se é isso mesmo.")

    return erros, avisos