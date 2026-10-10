from datetime import date

import streamlit as st

from src.assistant import regras
from src.assistant.alertas import gerar_alertas
from src.utils.alertas_ui import exibir_alerta

st.set_page_config(page_title="Assistente", page_icon="🤖")
st.title("Assistente")
st.caption(
    "Analisa seus lançamentos, orçamentos e metas do mês e aponta o que merece atenção, "
    "sempre com uma sugestão do que fazer."
)

with st.expander("Analisar outra data"):
    hoje = st.date_input("Data de referência", value=date.today(), format="DD/MM/YYYY")
    st.caption(
        "Útil para testar as regras. A análise usa todos os lançamentos já registrados, mesmo os "
        "posteriores à data escolhida; para revisar um mês passado, escolha o último dia dele."
    )

alertas = gerar_alertas(hoje)
st.subheader(f"Análise de {hoje:%m/%Y}")

c1, c2, c3 = st.columns(3)
c1.metric("🚨 Críticos", sum(a.nivel == "critico" for a in alertas))
c2.metric("⚠️ Atenção", sum(a.nivel == "atencao" for a in alertas))
c3.metric("💡 Informativos", sum(a.nivel == "info" for a in alertas))

if not alertas:
    st.success("Tudo certo por aqui: nenhum alerta para este mês. ✅")
for alerta in alertas:
    exibir_alerta(alerta)

with st.expander("Como o assistente decide"):
    st.write("O assistente segue regras fixas e transparentes, sem inteligência artificial:")
    for descricao in regras.descricao_das_regras():
        st.markdown(f"- {descricao}")
    st.caption(
        "Os limites (como 80% do orçamento ou 20% acima da média) ficam no topo do arquivo "
        "src/assistant/regras.py e podem ser ajustados."
    )