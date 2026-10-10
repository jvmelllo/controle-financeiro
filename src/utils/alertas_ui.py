import html

import streamlit as st

from src.assistant.regras import Alerta

# nível -> (ícone, cor RGB). O texto não usa essa cor: herda a cor normal do tema.
_ESTILO = {
    "critico": ("🚨", "239, 68, 68"),
    "atencao": ("⚠️", "234, 179, 8"),
    "info": ("💡", "59, 130, 246"),
}


def _texto(valor: str) -> str:
    """Protege o HTML e troca '$' por entidade, para 'R$ ... R$' não virar fórmula."""
    return html.escape(valor).replace("$", "&#36;")


def exibir_alerta(alerta: Alerta) -> None:
    """Mostra um alerta: fundo suave e faixa colorida à esquerda, com texto legível."""
    icone, rgb = _ESTILO[alerta.nivel]
    sugestao = (
        f'<div style="margin-top:0.4rem;">👉 {_texto(alerta.sugestao)}</div>'
        if alerta.sugestao
        else ""
    )
    st.markdown(
        f'<div style="background: rgba({rgb}, 0.14); border-left: 4px solid rgb({rgb}); '
        f'border-radius: 0.5rem; padding: 0.8rem 1rem; margin-bottom: 0.75rem; line-height: 1.5;">'
        f'<div style="font-weight: 700; font-size: 1.02rem;">{icone} {_texto(alerta.titulo)}</div>'
        f'<div style="margin-top: 0.3rem;">{_texto(alerta.mensagem)}</div>'
        f"{sugestao}</div>",
        unsafe_allow_html=True,
    )