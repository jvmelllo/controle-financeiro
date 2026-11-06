import streamlit as st

from src.database import repositories as repo
from src.utils.avisos import guardar_aviso, mostrar_aviso
from src.utils.campos import campo_valor
from src.utils.componentes import aviso_modo_demo
from src.utils.dinheiro import formatar_brl, reais_para_centavos

st.set_page_config(page_title="Cadastros", page_icon="🗂️")
st.title("Cadastros")
st.caption("Organize as categorias e as contas usadas nos seus lançamentos.")
aviso_modo_demo()

TIPOS_CONTA = {
    "carteira": "Carteira", "corrente": "Conta corrente",
    "poupanca": "Poupança", "cartao": "Cartão",
}


def bloco_de_categorias(tipo: str, titulo: str, categorias: list[dict]) -> None:
    """Uma coluna de categorias (entradas ou saídas): adicionar, renomear, desativar e reativar."""
    st.subheader(titulo)
    ativas = [c for c in categorias if c["ativa"]]
    inativas = [c for c in categorias if not c["ativa"]]

    with st.form(f"nova_categoria_{tipo}", clear_on_submit=True, border=False):
        campo, botao = st.columns([3, 1], vertical_alignment="bottom")
        nome = campo.text_input(
            "Nova categoria", max_chars=60, placeholder="Nome da nova categoria",
            label_visibility="collapsed",
        )
        adicionar = botao.form_submit_button("Criar")
    if adicionar:
        try:
            repo.criar_categoria(nome, tipo)
            guardar_aviso(f"Categoria '{nome.strip()}' criada.")
            st.rerun()
        except ValueError as erro:
            st.error(str(erro))

    if not ativas:
        st.caption("Nenhuma categoria ainda.")
    for c in ativas:
        col_nome, col_editar, col_desativar = st.columns([3, 1, 1], vertical_alignment="center")
        col_nome.write(c["nome"])
        with col_editar.popover(":material/edit:", help="Renomear"):
            novo_nome = st.text_input("Novo nome", value=c["nome"], max_chars=60, key=f"nome_{c['id']}")
            if st.button("Salvar nome", key=f"salvar_{c['id']}"):
                try:
                    repo.renomear_categoria(c["id"], novo_nome)
                    guardar_aviso("Categoria renomeada.")
                    st.rerun()
                except ValueError as erro:
                    st.error(str(erro))
        if col_desativar.button(":material/block:", key=f"desativar_{c['id']}", help="Desativar (mantém o histórico)"):
            try:
                repo.definir_categoria_ativa(c["id"], False)
            except ValueError as erro:
                st.toast(str(erro))  # a coluna do botão é estreita demais para uma caixa de erro
            else:
                guardar_aviso(f"Categoria '{c['nome']}' desativada.")
                st.rerun()

    if inativas:
        with st.expander(f"Desativadas ({len(inativas)})"):
            for c in inativas:
                col_nome, col_acao = st.columns([5, 2], vertical_alignment="center")
                col_nome.write(c["nome"])
                if col_acao.button("Reativar", key=f"reativar_{c['id']}"):
                    try:
                        repo.definir_categoria_ativa(c["id"], True)
                    except ValueError as erro:
                        st.toast(str(erro))
                    else:
                        guardar_aviso(f"Categoria '{c['nome']}' reativada.")
                        st.rerun()


aba_categorias, aba_contas = st.tabs(["Categorias", "Contas"])

# ---------- Categorias ----------
with aba_categorias:
    mostrar_aviso()
    st.caption(
        "Categorias organizam seus lançamentos (ex.: Alimentação, Transporte). Elas não são apagadas, "
        "para não quebrar o histórico: desative as que não usa mais."
    )
    categorias = repo.listar_categorias(apenas_ativas=False)
    col_entradas, col_saidas = st.columns(2, gap="large")
    with col_entradas:
        bloco_de_categorias("entrada", "Entradas", [c for c in categorias if c["tipo"] == "entrada"])
    with col_saidas:
        bloco_de_categorias("saida", "Saídas", [c for c in categorias if c["tipo"] == "saida"])

# ---------- Contas ----------
with aba_contas:
    mostrar_aviso("aviso_contas")
    st.caption(
        "Contas são de onde o dinheiro entra e sai (carteira, conta corrente...). "
        "O saldo inicial é quanto havia na conta antes do primeiro lançamento."
    )

    contas = repo.listar_contas()
    if not contas:
        st.info("Nenhuma conta cadastrada ainda. Crie a primeira abaixo.")
    for conta in contas:
        id_conta = conta["id"]
        with st.container(border=True):
            col_info, col_saldo, col_editar = st.columns([4, 3, 1], vertical_alignment="center")
            col_info.markdown(f"**{conta['nome']}**")
            col_info.caption(TIPOS_CONTA[conta["tipo"]])
            col_saldo.caption("Saldo inicial")
            col_saldo.write(formatar_brl(conta["saldo_inicial"]))
            with col_editar.popover(":material/edit:", help="Editar conta"):
                st.caption("Atenção: alterar o saldo inicial muda o saldo atual do app.")
                novo_nome = st.text_input(
                    "Nome", value=conta["nome"], max_chars=60, key=f"conta_nome_{id_conta}"
                )
                novo_saldo = st.number_input(
                    "Saldo inicial (R$)", value=conta["saldo_inicial"] / 100, step=10.0,
                    format="%.2f", key=f"conta_saldo_{id_conta}",
                )
                if st.button("Salvar conta", key=f"salvar_conta_{id_conta}"):
                    try:
                        repo.atualizar_conta(id_conta, novo_nome, reais_para_centavos(novo_saldo))
                        guardar_aviso("Conta atualizada.", "aviso_contas")
                        st.rerun()
                    except ValueError as erro:
                        st.error(str(erro))

    with st.expander("Nova conta", expanded=not contas):
        with st.form("nova_conta", clear_on_submit=True, border=False):
            nome_conta = st.text_input("Nome", max_chars=60, placeholder="Ex.: Conta corrente")
            tipo_conta = st.selectbox("Tipo", list(TIPOS_CONTA), format_func=TIPOS_CONTA.get)
            saldo_inicial = campo_valor("Saldo inicial (R$)", minimo=None, passo=10.0) or 0
            criar_conta = st.form_submit_button("Criar conta")
        if criar_conta:
            try:
                repo.criar_conta(nome_conta, tipo_conta, saldo_inicial)
                guardar_aviso(f"Conta '{nome_conta.strip()}' criada.", "aviso_contas")
                st.rerun()
            except ValueError as erro:
                st.error(str(erro))
