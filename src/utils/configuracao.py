"""Configuração do app: variáveis de ambiente (.env) e, na nuvem, os segredos do Streamlit.

No computador, tudo vem do arquivo .env. Na hospedagem (Streamlit Community Cloud) não existe
.env: os mesmos nomes são cadastrados em "Secrets" e lidos de `st.secrets`. A variável de
ambiente tem prioridade, então o que for definido no terminal vale sobre o resto.
"""

import os

_VERDADEIROS = {"1", "true", "sim", "yes", "on"}


def _segredo(nome: str) -> str | None:
    """Valor do segredo do Streamlit com esse nome, ou None se não houver (ou se não houver segredos)."""
    try:
        import streamlit as st

        valor = st.secrets.get(nome)
    except Exception:  # sem arquivo de segredos, o Streamlit levanta erro ao consultar
        return None
    return None if valor is None else str(valor)


def ler(nome: str, padrao: str | None = None) -> str | None:
    """Lê uma configuração: variável de ambiente primeiro, depois os segredos do Streamlit."""
    valor = os.getenv(nome)
    if valor in (None, ""):
        valor = _segredo(nome)
    return padrao if valor in (None, "") else valor


def modo_demo() -> bool:
    """True quando o app roda como demonstração pública: dados fictícios e somente leitura.

    Ativa com MODO_DEMO=1 (no .env ou nos segredos da hospedagem). No computador fica desligado.
    """
    return (ler("MODO_DEMO") or "").strip().lower() in _VERDADEIROS
