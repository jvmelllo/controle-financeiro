#streamlit run app.py
import streamlit as st

from src.services import fluxo_caixa
from src.utils.dinheiro import formatar_brl

st.set_page_config(page_title="Controle Financeiro", page_icon="💰")
st.title("Controle Financeiro")
st.metric("Saldo atual", formatar_brl(fluxo_caixa.saldo_atual()))
st.caption("Use o menu lateral para navegar.")