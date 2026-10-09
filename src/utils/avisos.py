import streamlit as st


def guardar_aviso(texto: str, chave: str = "aviso") -> None:
    """Guarda uma mensagem para aparecer depois do próximo st.rerun()."""
    st.session_state[chave] = texto


def mostrar_aviso(chave: str = "aviso") -> None:
    texto = st.session_state.pop(chave, None)
    if texto:
        st.success(texto)