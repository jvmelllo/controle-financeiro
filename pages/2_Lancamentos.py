from datetime import date

import pandas as pd
import streamlit as st

from src.database import repositories as repo
from src.services import fluxo_caixa
from src.services import metas as servico_metas
from src.services.validacoes import validar_lancamento
from src.utils.avisos import guardar_aviso, mostrar_aviso
from src.utils.campos import campo_valor
from src.utils.dinheiro import formatar_brl, reais_para_centavos


st.set_page_config(page_title="Lançamentos", page_icon="💸")
st.title("Lançamentos")

ROTULO_TIPO = {"entrada": "Entrada", "saida": "Saída"}
FORMAS = {
    "pix": "Pix", "debito": "Débito", "credito": "Crédito",
    "dinheiro": "Dinheiro", "outro": "Outro",
}
FORMAS_EDICAO = [None] + list(FORMAS)  # None = sem forma de pagamento informada
TODAS = {"id": None, "nome": "Todas"}


def indice_por_id(itens: list[dict], id_procurado: int) -> int:
    return next((i for i, item in enumerate(itens) if item["id"] == id_procurado), 0)


def rotulo(t: dict) -> str:
    texto = f"{t['data'].strftime('%d/%m/%Y')} · {t['categoria']} · {formatar_brl(t['valor'])}"
    return texto + (f" · {t['descricao']}" if t["descricao"] else "")


def editar_lancamento(t: dict) -> None:
    tid = t["id"]
    categorias = repo.listar_categorias(tipo=t["tipo"])
    if not any(c["id"] == t["categoria_id"] for c in categorias):
        categorias.append({"id": t["categoria_id"], "nome": f"{t['categoria']} (inativa)"})
    contas = repo.listar_contas()

    st.caption(f"Tipo: {ROTULO_TIPO[t['tipo']]}. Para mudar o tipo, exclua e lance de novo.")
    with st.form(f"editar_{tid}"):
        data = st.date_input("Data", value=t["data"], format="DD/MM/YYYY", key=f"e_data_{tid}")
        valor = st.number_input(
            "Valor (R$)", min_value=0.0, step=1.0, format="%.2f",
            value=t["valor"] / 100, key=f"e_valor_{tid}",
        )
        categoria = st.selectbox(
            "Categoria", categorias, index=indice_por_id(categorias, t["categoria_id"]),
            format_func=lambda c: c["nome"], key=f"e_cat_{tid}",
        )
        conta = st.selectbox(
            "Conta", contas, index=indice_por_id(contas, t["conta_id"]),
            format_func=lambda c: c["nome"], key=f"e_conta_{tid}",
        )
        forma = st.selectbox(
            "Forma de pagamento", FORMAS_EDICAO,
            index=FORMAS_EDICAO.index(t["forma_pagamento"]) if t["forma_pagamento"] in FORMAS_EDICAO else 0,
            format_func=lambda f: "—" if f is None else FORMAS[f], key=f"e_forma_{tid}",
        )
        descricao = st.text_input(
            "Descrição", value=t["descricao"] or "", max_chars=255, key=f"e_desc_{tid}"
        )
        salvar = st.form_submit_button("Salvar alterações")

    if salvar:
        centavos = reais_para_centavos(valor)
        erros, avisos = validar_lancamento(data, centavos)
        if erros:
            for erro in erros:
                st.error(erro)
        else:
            try:
                repo.atualizar_transacao(
                    tid, data=data, valor=centavos, categoria_id=categoria["id"],
                    conta_id=conta["id"], descricao=descricao.strip() or None,
                    forma_pagamento=forma,
                )
                guardar_aviso(" ".join(["Lançamento atualizado."] + avisos))
                st.rerun()
            except ValueError as erro:
                st.error(str(erro))

    with st.expander("Excluir este lançamento"):
        confirmar = st.checkbox(
            "Confirmo que quero excluir este lançamento. Não dá para desfazer.",
            key=f"confirmar_{tid}",
        )
        if st.button("Excluir lançamento", type="primary", disabled=not confirmar, key=f"excluir_{tid}"):
            repo.excluir_transacao(tid)
            guardar_aviso("Lançamento excluído.")
            st.rerun()


aba_novo, aba_historico = st.tabs(["Novo lançamento", "Histórico"])

# ---------- 3.1 Novo lançamento ----------
with aba_novo:
    mostrar_aviso("aviso_novo")

    # o tipo fica fora do formulário para a lista de categorias acompanhar a escolha
    tipo = st.radio("Tipo", list(ROTULO_TIPO), format_func=ROTULO_TIPO.get, horizontal=True)
    categorias = repo.listar_categorias(tipo=tipo)
    contas = repo.listar_contas()

    if not categorias or not contas:
        st.warning("Cadastre ao menos uma conta e uma categoria deste tipo (página Cadastros).")
    else:
        with st.form("novo_lancamento", clear_on_submit=True):
            data = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            centavos = campo_valor("Valor (R$)") or 0
            categoria = st.selectbox("Categoria", categorias, format_func=lambda c: c["nome"])
            conta = st.selectbox("Conta", contas, format_func=lambda c: c["nome"])
            forma = st.selectbox("Forma de pagamento", list(FORMAS), format_func=FORMAS.get)
            descricao = st.text_input("Descrição (opcional)", max_chars=255)
            salvar = st.form_submit_button("Salvar lançamento")

        if salvar:

            erros, avisos = validar_lancamento(data, centavos)
            if erros:
                for erro in erros:
                    st.error(erro)
            else:
                try:
                    repo.inserir_transacao(
                        data, centavos, tipo, categoria["id"], conta["id"],
                        descricao.strip() or None, forma,
                    )
                    for aviso in avisos:
                        st.warning(aviso)
                    st.success(f"{ROTULO_TIPO[tipo]} de {formatar_brl(centavos)} registrada.")
                    st.session_state["sugestoes_reserva"] = (
                        [{**s, "data": data} for s in servico_metas.sugestoes_de_reserva(centavos)]
                        if tipo == "entrada"
                        else []
                    )
                except ValueError as erro:
                    st.error(str(erro))

                # ---------- 5.4 Reserva sugerida a cada entrada ----------
    sugestoes = st.session_state.get("sugestoes_reserva", [])
    if sugestoes:
        st.divider()
        st.subheader("Reserva sugerida")
        for sugestao in sugestoes:
            col_texto, col_botao = st.columns([4, 1])
            col_texto.write(
                f"Separar **{formatar_brl(sugestao['valor'])}** "
                f"({sugestao['percentual']:g}% da entrada) para **{sugestao['meta']}**."
            )
            if col_botao.button("Registrar", key=f"reserva_{sugestao['meta_id']}"):
                try:
                    repo.inserir_aporte(sugestao["meta_id"], sugestao["data"], sugestao["valor"])
                    st.session_state["sugestoes_reserva"] = [
                        s for s in sugestoes if s["meta_id"] != sugestao["meta_id"]
                    ]
                    guardar_aviso(
                        f"Aporte de {formatar_brl(sugestao['valor'])} em {sugestao['meta']} registrado.",
                        "aviso_novo",
                    )
                    st.rerun()
                except ValueError as erro:
                    st.error(str(erro))
        if st.button("Dispensar sugestões"):
            st.session_state["sugestoes_reserva"] = []
            st.rerun()

# ---------- 3.2 Histórico com filtros + 3.3 edição e exclusão ----------
with aba_historico:
    mostrar_aviso()

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

        st.divider()
        st.subheader("Editar ou excluir")
        escolhida = st.selectbox(
            "Lançamento", transacoes, index=None,
            placeholder="Escolha um lançamento", format_func=rotulo,
        )
        if escolhida:
            editar_lancamento(escolhida)