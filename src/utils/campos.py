import streamlit as st

from src.utils.dinheiro import reais_para_centavos


def campo_valor(rotulo: str, minimo: float | None = 0.0, passo: float = 1.0, **kwargs) -> int | None:
    """Campo de valor em reais que começa vazio: digitar substitui, em vez de acrescentar ao zero.

    Devolve o valor em centavos, ou None enquanto o campo estiver vazio.
    Use minimo=None para permitir valores negativos.
    """
    valor = st.number_input(
        rotulo, value=None, min_value=minimo, step=passo, format="%.2f",
        placeholder="0,00", **kwargs,
    )
    return None if valor is None else reais_para_centavos(valor)