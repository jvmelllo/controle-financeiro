#streamlit run app.py
from datetime import date

import streamlit as st

from src.assistant.alertas import gerar_alertas
from src.database import repositories as repo
from src.services import fluxo_caixa
from src.utils.alertas_ui import exibir_alerta
from src.utils.datas import intervalo_do_mes
from src.utils.dinheiro import formatar_brl

st.set_page_config(page_title="Controle Financeiro", page_icon="💰")
st.title("Controle Financeiro")
st.caption("Fluxo de caixa, orçamento, metas e um assistente para gastar com mais consciência.")

hoje = date.today()
inicio, fim = intervalo_do_mes(f"{hoje.year:04d}-{hoje.month:02d}")
saldo = fluxo_caixa.saldo_atual()
reservado = repo.total_reservado()
resumo = fluxo_caixa.resumo_do_periodo(inicio, fim)

c1, c2, c3 = st.columns(3)
c1.metric("Saldo atual", formatar_brl(saldo))
c2.metric(
    "Livre para gastar",
    formatar_brl(saldo - reservado),
    help="Saldo atual menos o que já foi separado nas metas.",
)
c3.metric("Resultado do mês", formatar_brl(resumo["resultado"]), help="Entradas menos saídas do mês atual.")

importantes = [a for a in gerar_alertas() if a.nivel != "info"]
if importantes:
    st.subheader("Atenção")
    for alerta in importantes[:2]:
        exibir_alerta(alerta)
    if len(importantes) > 2:
        st.caption(f"Mais {len(importantes) - 2} alerta(s) na página Assistente.")

ATALHOS = [
    ("pages/1_Dashboard.py", "Dashboard", "Saldo, gráficos e evolução do período."),
    ("pages/2_Lancamentos.py", "Lançamentos", "Registre entradas e saídas e consulte o histórico."),
    ("pages/3_Orcamento_e_Metas.py", "Orçamento e metas", "Limites por categoria e reservas."),
    ("pages/4_Assistente.py", "Assistente", "Alertas e sugestões para gastar melhor."),
    ("pages/5_Importar_Dados.py", "Importar dados", "Traga lançamentos de uma planilha CSV."),
    ("pages/6_Cadastros.py", "Cadastros", "Categorias e contas."),
]

st.subheader("Ir para")
for primeiro in range(0, len(ATALHOS), 3):
    colunas = st.columns(3)
    for coluna, (pagina, nome, descricao) in zip(colunas, ATALHOS[primeiro:primeiro + 3]):
        with coluna.container(border=True):
            st.markdown(f"### {nome}")
            st.caption(descricao)
            st.page_link(pagina, label="Abrir", width="stretch")
