import streamlit as st

from src.database import repositories as repo
from src.utils.avisos import guardar_aviso, mostrar_aviso
from src.utils.campos import campo_valor
from src.utils.dinheiro import formatar_brl, reais_para_centavos

st.set_page_config(page_title="Cadastros", page_icon="🗂️")
st.title("Cadastros")

TIPOS_CATEGORIA = {"entrada": "Entrada", "saida": "Saída"}
TIPOS_CONTA = {
    "carteira": "Carteira", "corrente": "Conta corrente",
    "poupanca": "Poupança", "cartao": "Cartão",
}

aba_categorias, aba_contas = st.tabs(["Categorias", "Contas"])

# ---------- Categorias ----------
with aba_categorias:
    mostrar_aviso()

    st.subheader("Nova categoria")
    with st.form("nova_categoria", clear_on_submit=True):
        nome = st.text_input("Nome", max_chars=60)
        tipo = st.radio("Tipo", list(TIPOS_CATEGORIA), format_func=TIPOS_CATEGORIA.get, horizontal=True)
        criar = st.form_submit_button("Criar categoria")
    if criar:
        try:
            repo.criar_categoria(nome, tipo)
            guardar_aviso(f"Categoria '{nome.strip()}' criada.")
            st.rerun()
        except ValueError as erro:
            st.error(str(erro))

    st.subheader("Categorias existentes")
    categorias = repo.listar_categorias(apenas_ativas=False)
    for c in categorias:
        col_nome, col_tipo, col_acao = st.columns([3, 2, 2])
        col_nome.write(c["nome"] + ("" if c["ativa"] else " (inativa)"))
        col_tipo.write(TIPOS_CATEGORIA[c["tipo"]])
        rotulo_botao = "Desativar" if c["ativa"] else "Reativar"
        if col_acao.button(rotulo_botao, key=f"ativa_{c['id']}"):
            repo.definir_categoria_ativa(c["id"], not c["ativa"])
            st.rerun()
    st.caption(
        "Categorias não são apagadas para não quebrar o histórico: desative as que não usa mais."
    )

    if categorias:
        with st.expander("Renomear categoria"):
            alvo = st.selectbox(
                "Categoria", categorias, format_func=lambda c: c["nome"], key="renomear_alvo"
            )
            novo_nome = st.text_input("Novo nome", max_chars=60, key="renomear_nome")
            if st.button("Renomear"):
                try:
                    repo.renomear_categoria(alvo["id"], novo_nome)
                    guardar_aviso("Categoria renomeada.")
                    st.rerun()
                except ValueError as erro:
                    st.error(str(erro))

# ---------- Contas ----------
with aba_contas:
    mostrar_aviso("aviso_contas")

    st.subheader("Nova conta")
    with st.form("nova_conta", clear_on_submit=True):
        nome_conta = st.text_input("Nome", max_chars=60)
        tipo_conta = st.selectbox("Tipo", list(TIPOS_CONTA), format_func=TIPOS_CONTA.get)
        saldo_inicial = campo_valor("Saldo inicial (R$)", minimo=None, passo=10.0) or 0
        criar_conta = st.form_submit_button("Criar conta")
    if criar_conta:
        try:
            repo.criar_conta(nome_conta, tipo_conta, saldo_inicial)
            st.success(f"Conta '{nome_conta.strip()}' criada.")
        except ValueError as erro:
            st.error(str(erro))

    st.subheader("Contas existentes")
    contas = repo.listar_contas()
    if not contas:
        st.info("Nenhuma conta cadastrada ainda.")
    else:
        st.dataframe(
            [
                {
                    "Nome": c["nome"],
                    "Tipo": TIPOS_CONTA[c["tipo"]],
                    "Saldo inicial": formatar_brl(c["saldo_inicial"]),
                }
                for c in contas
            ],
            hide_index=True,
        )
        with st.expander("Editar conta"):
            st.caption("Atenção: alterar o saldo inicial muda o saldo atual do app.")
            conta_alvo = st.selectbox(
                "Conta", contas, format_func=lambda c: c["nome"], key="editar_conta_alvo"
            )
            id_conta = conta_alvo["id"]
            novo_nome_conta = st.text_input(
                "Nome", value=conta_alvo["nome"], max_chars=60, key=f"conta_nome_{id_conta}"
            )
            novo_saldo = st.number_input(
                "Saldo inicial (R$)", value=conta_alvo["saldo_inicial"] / 100, step=10.0,
                format="%.2f", key=f"conta_saldo_{id_conta}",
            )
            if st.button("Salvar conta", key=f"salvar_conta_{id_conta}"):
                try:
                    repo.atualizar_conta(id_conta, novo_nome_conta, reais_para_centavos(novo_saldo))
                    guardar_aviso("Conta atualizada.", "aviso_contas")
                    st.rerun()
                except ValueError as erro:
                    st.error(str(erro))