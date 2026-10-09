from datetime import date

import pandas as pd
import streamlit as st

from src.database import repositories as repo
from src.services import fluxo_caixa
from src.utils.dinheiro import formatar_brl, reais_para_centavos

st.set_page_config(page_title="Lançamentos", page_icon="💸")
st.title("Lançamentos")

ROTULO_TIPO = {"entrada": "Entrada", "saida": "Saída"}
FORMAS = {
    "pix": "Pix", "debito": "Débito", "credito": "Crédito",
    "dinheiro": "Dinheiro", "outro": "Outro",
}
TODAS = {"id": None, "nome": "Todas"}

aba_novo, aba_historico = st.tabs(["Novo lançamento", "Histórico"])

# ---------- 3.1 Novo lançamento ----------
with aba_novo:
    # o tipo fica fora do formulário para a lista de categorias acompanhar a escolha
    tipo = st.radio("Tipo", list(ROTULO_TIPO), format_func=ROTULO_TIPO.get, horizontal=True)
    categorias = repo.listar_categorias(tipo=tipo)
    contas = repo.listar_contas()

    if not categorias or not contas:
        st.warning("Cadastre ao menos uma conta e uma categoria deste tipo antes de lançar.")
    else:
        with st.form("novo_lancamento", clear_on_submit=True):
            data = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            valor = st.number_input("Valor (R$)", min_value=0.0, step=1.0, format="%.2f")
            categoria = st.selectbox("Categoria", categorias, format_func=lambda c: c["nome"])
            conta = st.selectbox("Conta", contas, format_func=lambda c: c["nome"])
            forma = st.selectbox("Forma de pagamento", list(FORMAS), format_func=FORMAS.get)
            descricao = st.text_input("Descrição (opcional)", max_chars=255)
            salvar = st.form_submit_button("Salvar lançamento")

        if salvar:
            if valor <= 0:
                st.error("Informe um valor maior que zero.")
            else:
                try:
                    centavos = reais_para_centavos(valor)
                    repo.inserir_transacao(
                        data, centavos, tipo, categoria["id"], conta["id"],
                        descricao.strip() or None, forma,
                    )
                    st.success(f"{ROTULO_TIPO[tipo]} de {formatar_brl(centavos)} registrada.")
                except ValueError as erro:
                    st.error(str(erro))

# ---------- 3.2 Histórico com filtros ----------
with aba_historico:
    meses = sorted(
        {linha["mes"] for linha in fluxo_caixa.totais_mensais()} | {date.today().strftime("%Y-%m")},
        reverse=True,
    )
    col1, col2, col3 = st.columns(3)
    mes = col1.selectbox(
        "Mês", meses + ["Todos"],
        format_func=lambda m: m if m == "Todos" else f"{m[5:]}/{m[:4]}",
    )
    tipo_filtro = col2.selectbox(
        "Tipo", ["Todos", "entrada", "saida"],
        format_func=lambda t: "Todos" if t == "Todos" else ROTULO_TIPO[t],
    )
    categoria_filtro = col3.selectbox(
        "Categoria", [TODAS] + repo.listar_categorias(apenas_ativas=False),
        format_func=lambda c: c["nome"],
    )

    transacoes = repo.listar_transacoes(
        mes=None if mes == "Todos" else mes,
        tipo=None if tipo_filtro == "Todos" else tipo_filtro,
        categoria_id=categoria_filtro["id"],
    )

    if not transacoes:
        st.info("Nenhum lançamento encontrado com esses filtros.")
    else:
        entradas = sum(t["valor"] for t in transacoes if t["tipo"] == "entrada")
        saidas = sum(t["valor"] for t in transacoes if t["tipo"] == "saida")
        m1, m2, m3 = st.columns(3)
        m1.metric("Entradas", formatar_brl(entradas))
        m2.metric("Saídas", formatar_brl(saidas))
        m3.metric("Resultado", formatar_brl(entradas - saidas))

        tabela = pd.DataFrame([
            {
                "Data": t["data"].strftime("%d/%m/%Y"),
                "Tipo": ROTULO_TIPO[t["tipo"]],
                "Categoria": t["categoria"],
                "Conta": t["conta"],
                "Descrição": t["descricao"] or "",
                "Pagamento": FORMAS.get(t["forma_pagamento"], ""),
                "Valor": formatar_brl(t["valor"]),
            }
            for t in transacoes
        ])
        st.caption(f"{len(transacoes)} lançamento(s)")
        st.dataframe(tabela, hide_index=True)