from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def reais_para_centavos(valor) -> int:
    """Converte '1.234,56', 'R$ 10,10', '1234.56', 12.5 ou Decimal em centavos (int).

    Texto com vírgula: o ponto vira separador de milhar e a vírgula o decimal.
    Texto sem vírgula: o ponto é tratado como decimal ('1234.56').
    """
    if isinstance(valor, str):
        texto = valor.strip().replace("R$", "").replace(" ", "")
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        valor = texto
    try:
        decimal = Decimal(str(valor))
    except InvalidOperation:
        raise ValueError(f"Valor monetário inválido: {valor!r}")
    if not decimal.is_finite():
        raise ValueError(f"Valor monetário inválido: {valor!r}")
    return int((decimal * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def centavos_para_reais(centavos: int) -> Decimal:
    return Decimal(centavos) / 100


def formatar_brl(centavos: int) -> str:
    """123456 -> 'R$ 1.234,56'; -5000 -> '-R$ 50,00'."""
    sinal = "-" if centavos < 0 else ""
    reais, cents = divmod(abs(centavos), 100)
    return f"{sinal}R$ {reais:,}".replace(",", ".") + f",{cents:02d}"

def escapar_markdown(texto: str) -> str:
    """Escapa o '$' para o Streamlit não tratar 'R$ ... R$' como fórmula matemática."""
    return texto.replace("$", r"\$")