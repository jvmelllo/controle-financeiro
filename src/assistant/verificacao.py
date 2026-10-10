"""Confere se os valores em reais citados pela IA aparecem no resumo que ela recebeu.

Modelos pequenos erram contas e às vezes inventam números. Esta checagem não corrige a
resposta; ela só avisa quando um valor citado não está nos dados, para o usuário conferir.
"""

import re

from src.utils.dinheiro import formatar_brl

# "R$ 1.234,56", "R$1234,5", "R$ 80" (com ou sem centavos, com ou sem separador de milhar)
_VALOR = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?")


def valores_em_centavos(texto: str) -> list[int]:
    """Todos os valores 'R$ ...' do texto, em centavos, na ordem em que aparecem."""
    valores = []
    for inteiro, centavos in _VALOR.findall(texto):
        reais = int(inteiro.replace(".", ""))
        valores.append(reais * 100 + int((centavos or "0").ljust(2, "0")))
    return valores


def valores_fora_dos_dados(resposta: str, contexto: str) -> list[str]:
    """Valores citados na resposta que não aparecem no contexto, já formatados (sem repetição)."""
    conhecidos = set(valores_em_centavos(contexto))
    fora = []
    for valor in valores_em_centavos(resposta):
        texto = formatar_brl(valor)
        if valor not in conhecidos and texto not in fora:
            fora.append(texto)
    return fora
