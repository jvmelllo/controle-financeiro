import streamlit as st

from src.utils import configuracao
from src.utils.tema import AZUL

REPOSITORIO = "https://github.com/jvmelllo/controle-financeiro"


def barra_de_progresso(percentual: float, cor: str = AZUL) -> None:
    """Barra fina que preenche até `percentual` (0 a 100) na cor dada.

    O st.progress sempre usa a cor de destaque do tema; esta deixa escolher a cor
    (verde, amarelo ou vermelho conforme a situação do orçamento).
    O fundo da barra é um cinza translúcido, que funciona no tema claro e no escuro.
    """
    largura = max(0.0, min(float(percentual), 100.0))
    st.markdown(
        '<div role="progressbar" aria-valuemin="0" aria-valuemax="100" '
        f'aria-valuenow="{largura:.0f}" style="background: rgba(128, 128, 128, 0.25); '
        'border-radius: 999px; height: 0.6rem; overflow: hidden; margin: 0.25rem 0 0.4rem 0;">'
        f'<div style="width: {largura:.1f}%; height: 100%; background: {cor}; '
        'border-radius: 999px;"></div></div>',
        unsafe_allow_html=True,
    )


def aviso_modo_demo() -> None:
    """Faixa no topo das telas quando o app roda como demonstração pública (somente leitura)."""
    if configuracao.modo_demo():
        st.info(
            "Demonstração com dados fictícios e somente leitura: nada que você fizer aqui é salvo. "
            f"O projeto completo, com o passo a passo para rodar no seu computador, está no [GitHub]({REPOSITORIO})."
        )
