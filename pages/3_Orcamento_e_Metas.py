from datetime import date

import streamlit as st

from src.database import repositories as repo
from src.services import fluxo_caixa, orcamento
from src.utils.avisos import guardar_aviso, mostrar_aviso
from src.utils.campos import campo_valor
from src.utils.datas import deslocar_meses, rotulo_mes
from src.utils.dinheiro import formatar_brl, reais_para_centavos

st.set_page_config(page_title="Orçamento e metas", page_icon="🎯", layout="wide")
st.title("Orçamento e metas")

HOJE = date.today()
ICONES = {"ok": "🟢", "atencao": "🟡", "estourado": "🔴"}

aba_orcamento, aba_metas = st.tabs(["Orçamento do mês", "Metas de reserva"])

# ---------- 5.1 Orçamento por categoria ----------
with aba_orcamento:
    mostrar_aviso()

    mes_atual = HOJE.strftime("%Y-%m")
    proximo_mes = deslocar_meses(HOJE, 1).strftime("%Y-%m")
    meses = sorted(
        {t["mes"] for t in fluxo_caixa.totais_mensais()} | {mes_atual, proximo_mes}, reverse=True
    )
    mes = st.selectbox("Mês", meses, index=meses.index(mes_atual), format_func=rotulo_mes)
    mes_anterior = deslocar_meses(date(int(mes[:4]), int(mes[5:]), 1), -1).strftime("%Y-%m")

    status = orcamento.status_do_orcamento(mes)

    if status["itens"]:
        c1, c2, c3 = st.columns(3)
        c1.metric("Limite total", formatar_brl(status["limite_total"]))
        c2.metric("Gasto nas categorias com limite", formatar_brl(status["gasto_orcado"]))
        c3.metric(
            "Gasto sem limite definido", formatar_brl(status["gasto_fora_do_orcamento"]),
            help="Gastos de categorias que ainda não têm limite neste mês.",
        )

        for item in status["itens"]:
            st.markdown(f"**{ICONES[item['situacao']]} {item['categoria']}**")
            st.progress(
                min(item["percentual"], 100) / 100,
                text=(
                    f"{formatar_brl(item['gasto'])} de {formatar_brl(item['limite'])} "
                    f"({item['percentual']:.0f}%)"
                ),
            )
            if item["restante"] < 0:
                st.caption(f"Estourou em {formatar_brl(-item['restante'])}.")
            else:
                st.caption(f"Restam {formatar_brl(item['restante'])}.")
    else:
        st.info("Nenhum limite definido para este mês. Defina abaixo ou copie do mês anterior.")

    st.divider()
    st.subheader("Definir limite")
    categorias = repo.listar_categorias(tipo="saida")
    if not categorias:
        st.warning("Cadastre categorias de saída na página Cadastros.")
    else:
        with st.form("definir_limite", clear_on_submit=True):
            categoria = st.selectbox("Categoria", categorias, format_func=lambda c: c["nome"])
            centavos = campo_valor("Limite do mês (R$)", passo=50.0) or 0
            salvar = st.form_submit_button("Salvar limite")
        st.caption("Se a categoria já tem limite neste mês, o valor novo substitui o anterior.")

        if salvar:
            if centavos <= 0:
                st.error("Informe um limite maior que zero.")
            else:
                try:
                    repo.definir_orcamento(categoria["id"], mes, centavos)
                    guardar_aviso(f"Limite de {categoria['nome']}: {formatar_brl(centavos)}.")
                    st.rerun()
                except ValueError as erro:
                    st.error(str(erro))

    if st.button(f"Copiar limites de {rotulo_mes(mes_anterior)}"):
        copiados = repo.copiar_orcamentos(mes_anterior, mes)
        guardar_aviso(
            f"{copiados} limite(s) copiado(s)."
            if copiados
            else "Nada para copiar: o mês anterior não tem limites ou eles já estão definidos aqui."
        )
        st.rerun()

    if status["itens"]:
        with st.expander("Remover um limite"):
            alvo = st.selectbox(
                "Categoria", status["itens"], format_func=lambda i: i["categoria"], key="remover_alvo"
            )
            if st.button("Remover limite"):
                repo.remover_orcamento(alvo["categoria_id"], mes)
                guardar_aviso(f"Limite de {alvo['categoria']} removido.")
                st.rerun()

# ---------- 5.2 a 5.4 Metas (próximo passo) ----------
with aba_metas:
    st.info("As metas de reserva chegam no próximo passo.")