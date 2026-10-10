from dataclasses import dataclass
from datetime import date, timedelta

import streamlit as st

from src.charts import graficos
from src.services import fluxo_caixa
from src.utils.datas import (
    intervalo_do_ano,
    intervalo_do_mes,
    intervalo_do_trimestre,
    periodo_anterior,
    rotulo_mes,
)
from src.utils.dinheiro import formatar_brl

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
st.title("Dashboard")

HOJE = date.today()


@dataclass
class Periodo:
    rotulo: str
    inicio: date          # inclusivo
    fim: date             # exclusivo
    meses: int | None = None   # 1, 3 ou 12 quando o período fecha em meses
    comparar: bool = True      # se há período anterior para comparar


def escolher_periodo() -> Periodo:
    meses_com_dados = sorted({t["mes"] for t in fluxo_caixa.totais_mensais()}, reverse=True)
    mes_atual = HOJE.strftime("%Y-%m")
    if mes_atual not in meses_com_dados:
        meses_com_dados.insert(0, mes_atual)
    anos = sorted({int(m[:4]) for m in meses_com_dados}, reverse=True)

    tipo = st.radio(
        "Período", ["Mês", "Trimestre", "Ano", "Personalizado", "Tudo"], horizontal=True
    )

    if tipo == "Mês":
        mes = st.selectbox("Mês", meses_com_dados, format_func=rotulo_mes)
        inicio, fim = intervalo_do_mes(mes)
        return Periodo(rotulo_mes(mes), inicio, fim, meses=1)

    if tipo == "Trimestre":
        col_ano, col_tri = st.columns(2)
        ano = col_ano.selectbox("Ano", anos)
        tri_padrao = (HOJE.month - 1) // 3 if ano == HOJE.year else 0
        tri = col_tri.selectbox("Trimestre", [1, 2, 3, 4], index=tri_padrao, format_func=lambda t: f"T{t}")
        inicio, fim = intervalo_do_trimestre(ano, tri)
        return Periodo(f"T{tri}/{ano}", inicio, fim, meses=3)

    if tipo == "Ano":
        ano = st.selectbox("Ano", anos)
        inicio, fim = intervalo_do_ano(ano)
        return Periodo(str(ano), inicio, fim, meses=12)

    if tipo == "Personalizado":
        col_de, col_ate = st.columns(2)
        de = col_de.date_input("De", value=HOJE.replace(day=1), format="DD/MM/YYYY")
        ate = col_ate.date_input("Até", value=HOJE, format="DD/MM/YYYY")
        if ate < de:
            st.error("A data final não pode ser anterior à inicial.")
            st.stop()
        return Periodo(f"{de:%d/%m/%Y} a {ate:%d/%m/%Y}", de, ate + timedelta(days=1))

    return Periodo("Todo o histórico", date(2000, 1, 1), date(2100, 1, 1), comparar=False)


periodo = escolher_periodo()
st.subheader(periodo.rotulo)

# ---------- 4.1 Cartões de resumo ----------
resumo = fluxo_caixa.resumo_do_periodo(periodo.inicio, periodo.fim)
anterior = None
if periodo.comparar:
    inicio_ant, fim_ant = periodo_anterior(periodo.inicio, periodo.fim, periodo.meses)
    anterior = fluxo_caixa.resumo_do_periodo(inicio_ant, fim_ant)


def variacao(chave: str) -> str | None:
    if anterior is None:
        return None
    pct = fluxo_caixa.variacao_percentual(resumo[chave], anterior[chave])
    return None if pct is None else f"{pct:+.1f}%".replace(".", ",")


c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Saldo atual", formatar_brl(fluxo_caixa.saldo_atual()))
c2.metric("Entradas", formatar_brl(resumo["entradas"]), delta=variacao("entradas"))
c3.metric("Saídas", formatar_brl(resumo["saidas"]), delta=variacao("saidas"), delta_color="inverse")
c4.metric("Resultado", formatar_brl(resumo["resultado"]), delta=variacao("resultado"))
sobra = (
    f"{resumo['resultado'] / resumo['entradas'] * 100:.0f}%" if resumo["entradas"] > 0 else "—"
)
c5.metric("Sobra do período", sobra, help="Quanto das entradas sobrou: resultado ÷ entradas.")
if anterior is not None:
    st.caption("As variações comparam com o período imediatamente anterior.")

# ---------- 4.2 e 4.3 Gastos por categoria e entradas × saídas ----------
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Gastos por categoria")
    formato = st.radio(
        "Formato", ["Rosca", "Barras"], horizontal=True, label_visibility="collapsed"
    )
    gastos = fluxo_caixa.gastos_por_categoria_no_periodo(periodo.inicio, periodo.fim)
    if gastos:
        st.plotly_chart(graficos.gastos_por_categoria(gastos, formato.lower()))
    else:
        st.info("Sem gastos neste período.")

with col_b:
    st.subheader("Entradas × saídas por mês")
    totais = fluxo_caixa.totais_mensais(periodo.inicio, periodo.fim)
    if totais:
        st.plotly_chart(graficos.entradas_vs_saidas(totais))
    else:
        st.info("Sem movimentações neste período.")

# ---------- 4.4 Evolução do saldo ----------
st.subheader("Evolução do saldo")
evolucao = fluxo_caixa.evolucao_do_saldo(periodo.inicio, periodo.fim)
if evolucao:
    st.plotly_chart(graficos.evolucao_do_saldo(evolucao))
else:
    st.info("Sem movimentações neste período.")