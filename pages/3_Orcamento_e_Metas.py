from datetime import date

import streamlit as st

from src.database import repositories as repo
from src.services import fluxo_caixa, orcamento
from src.services import metas as servico_metas
from src.utils.avisos import guardar_aviso, mostrar_aviso
from src.utils.campos import campo_valor
from src.utils.componentes import barra_de_progresso
from src.utils.datas import deslocar_meses, rotulo_mes
from src.utils.dinheiro import escapar_markdown, formatar_brl, reais_para_centavos
from src.utils.tema import AMARELO, AZUL, COR_DA_SITUACAO, VERDE

st.set_page_config(page_title="Orçamento e metas", page_icon="🎯", layout="wide")
st.title("Orçamento e metas")
st.caption("Defina limites de gasto por categoria e acompanhe as reservas das suas metas.")

HOJE = date.today()


def manter_aberta(meta_id: int) -> None:
    """Mantém os detalhes da meta abertos depois do st.rerun()."""
    st.session_state.setdefault("metas_abertas", set()).add(meta_id)


def em_grade(itens: list, desenhar) -> None:
    """Distribui os cartões em duas colunas (da esquerda para a direita, linha a linha)."""
    colunas = st.columns(2, gap="large")
    for posicao, item in enumerate(itens):
        with colunas[posicao % 2]:
            desenhar(item)


# ---------- 5.1 Orçamento por categoria ----------
def cartao_do_limite(item: dict, mes: str) -> None:
    """Um limite do mês: situação, barra de uso e as ações de alterar ou remover."""
    categoria_id = item["categoria_id"]
    with st.container(border=True):
        col_nome, col_acao = st.columns([5, 1], vertical_alignment="center")
        col_nome.markdown(f"**{escapar_markdown(item['categoria'])}**")
        with col_acao.popover(":material/edit:", help="Alterar ou remover o limite"):
            novo_limite = st.number_input(
                "Limite do mês (R$)", min_value=0.0, step=50.0, format="%.2f",
                value=item["limite"] / 100, key=f"limite_{mes}_{categoria_id}",
            )
            if st.button("Salvar limite", type="primary", key=f"salvar_limite_{mes}_{categoria_id}"):
                centavos = reais_para_centavos(novo_limite)
                if centavos <= 0:
                    st.error("Informe um limite maior que zero.")
                else:
                    try:
                        repo.definir_orcamento(categoria_id, mes, centavos)
                        guardar_aviso(f"Limite de {item['categoria']}: {formatar_brl(centavos)}.")
                        st.rerun()
                    except ValueError as erro:
                        st.error(str(erro))
            if st.button("Remover limite", key=f"remover_limite_{mes}_{categoria_id}"):
                repo.remover_orcamento(categoria_id, mes)
                guardar_aviso(f"Limite de {item['categoria']} removido.")
                st.rerun()

        barra_de_progresso(item["percentual"], COR_DA_SITUACAO[item["situacao"]])
        st.markdown(escapar_markdown(
            f"**{formatar_brl(item['gasto'])}** de {formatar_brl(item['limite'])} "
            f"({item['percentual']:.0f}%)"
        ))
        if item["restante"] < 0:
            st.caption(escapar_markdown(f"Estourou em {formatar_brl(-item['restante'])}."))
        else:
            st.caption(escapar_markdown(f"Restam {formatar_brl(item['restante'])}."))


aba_orcamento, aba_metas = st.tabs(["Orçamento do mês", "Metas de reserva"])

with aba_orcamento:
    mostrar_aviso()

    mes_atual = HOJE.strftime("%Y-%m")
    proximo_mes = deslocar_meses(HOJE, 1).strftime("%Y-%m")
    meses = sorted(
        {t["mes"] for t in fluxo_caixa.totais_mensais()} | {mes_atual, proximo_mes}, reverse=True
    )
    col_mes, col_copiar = st.columns([2, 3], vertical_alignment="bottom")
    mes = col_mes.selectbox("Mês", meses, index=meses.index(mes_atual), format_func=rotulo_mes)
    mes_anterior = deslocar_meses(date(int(mes[:4]), int(mes[5:]), 1), -1).strftime("%Y-%m")
    if col_copiar.button(f"Copiar limites de {rotulo_mes(mes_anterior)}"):
        copiados = repo.copiar_orcamentos(mes_anterior, mes)
        guardar_aviso(
            f"{copiados} limite(s) copiado(s)."
            if copiados
            else "Nada para copiar: o mês anterior não tem limites ou eles já estão definidos aqui."
        )
        st.rerun()

    status = orcamento.status_do_orcamento(mes)

    if status["itens"]:
        c1, c2, c3 = st.columns(3)
        c1.metric("Limite total", formatar_brl(status["limite_total"]))
        c2.metric("Gasto nas categorias com limite", formatar_brl(status["gasto_orcado"]))
        c3.metric(
            "Gasto sem limite definido", formatar_brl(status["gasto_fora_do_orcamento"]),
            help="Gastos de categorias que ainda não têm limite neste mês.",
        )

        st.subheader("Limites por categoria")
        st.caption("Do maior uso para o menor. Use o lápis para alterar ou remover um limite.")
        em_grade(status["itens"], lambda item: cartao_do_limite(item, mes))
    else:
        st.info(
            "Nenhum limite definido para este mês. Defina um logo abaixo "
            "ou copie os do mês anterior (botão acima)."
        )

    categorias = repo.listar_categorias(tipo="saida")
    with st.expander("Definir limite para uma categoria", expanded=not status["itens"]):
        if not categorias:
            st.warning("Cadastre categorias de saída na página Cadastros.")
        else:
            with st.form("definir_limite", clear_on_submit=True, border=False):
                col_categoria, col_limite, col_salvar = st.columns([4, 3, 2], vertical_alignment="bottom")
                categoria = col_categoria.selectbox(
                    "Categoria", categorias, format_func=lambda c: c["nome"]
                )
                with col_limite:
                    centavos = campo_valor("Limite do mês (R$)", passo=50.0) or 0
                salvar = col_salvar.form_submit_button("Salvar", type="primary")
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


# ---------- 5.2 e 5.3 Metas de reserva ----------
def cartao_da_meta(meta: dict) -> None:
    """Uma meta: andamento sempre visível; contribuir num clique; histórico e edição recolhidos."""
    mid = meta["id"]
    progresso = servico_metas.progresso_da_meta(meta)
    if progresso["concluida"]:
        cor = VERDE
    elif progresso["atrasada"]:
        cor = AMARELO
    else:
        cor = AZUL

    with st.container(border=True):
        col_nome, col_contribuir = st.columns([3, 2], vertical_alignment="center")
        col_nome.markdown(f"**{escapar_markdown(meta['nome'])}**")
        with col_contribuir.popover("Contribuir"):
            with st.form(f"contribuicao_{mid}", clear_on_submit=True, border=False):
                data_contribuicao = st.date_input(
                    "Data", value=HOJE, format="DD/MM/YYYY", key=f"contrib_data_{mid}"
                )
                valor_contribuicao = campo_valor(
                    "Valor da contribuição (R$)", key=f"contrib_valor_{mid}"
                ) or 0
                registrar = st.form_submit_button("Registrar contribuição", type="primary")
            if registrar:
                if valor_contribuicao <= 0:
                    st.error("Informe um valor maior que zero.")
                else:
                    try:
                        repo.inserir_aporte(mid, data_contribuicao, valor_contribuicao)
                        manter_aberta(mid)
                        guardar_aviso(
                            f"Contribuição de {formatar_brl(valor_contribuicao)} "
                            f"em {meta['nome']} registrada.",
                            "aviso_metas",
                        )
                        st.rerun()
                    except ValueError as erro:
                        st.error(str(erro))

        barra_de_progresso(progresso["percentual"], cor)
        st.markdown(escapar_markdown(
            f"**{formatar_brl(meta['aportado'])}** de {formatar_brl(meta['valor_alvo'])} "
            f"({progresso['percentual']:.0f}%)"
        ))
        detalhes = []
        if progresso["concluida"]:
            detalhes.append("Meta concluída")
        if meta["prazo"]:
            detalhes.append(f"Prazo: {meta['prazo']:%d/%m/%Y}")
        if progresso["atrasada"]:
            detalhes.append("Prazo vencido")
        if progresso["por_mes"]:
            detalhes.append(f"para chegar lá: cerca de {formatar_brl(progresso['por_mes'])} por mês")
        if meta["percentual_entrada"] > 0:
            detalhes.append(f"{meta['percentual_entrada']:g}% de cada entrada")
        if detalhes:
            st.caption(escapar_markdown(" · ".join(detalhes)))

        with st.expander("Histórico e edição", expanded=mid in st.session_state.get("metas_abertas", set())):
            aba_historico_meta, aba_editar = st.tabs(["Histórico", "Editar"])

            with aba_historico_meta:
                contribuicoes = repo.listar_aportes(mid)
                if not contribuicoes:
                    st.caption("Nenhuma contribuição ainda.")
                for contribuicao in contribuicoes[:20]:
                    col_data, col_valor, col_acao = st.columns([3, 3, 1], vertical_alignment="center")
                    col_data.write(f"{contribuicao['data']:%d/%m/%Y}")
                    col_valor.write(escapar_markdown(formatar_brl(contribuicao["valor"])))
                    if col_acao.button(
                        ":material/delete:", key=f"excluir_contribuicao_{contribuicao['id']}",
                        help="Excluir esta contribuição",
                    ):
                        repo.excluir_aporte(contribuicao["id"])
                        manter_aberta(mid)
                        guardar_aviso("Contribuição excluída.", "aviso_metas")
                        st.rerun()
                if len(contribuicoes) > 20:
                    st.caption(f"Mostrando as 20 mais recentes de {len(contribuicoes)}.")

            with aba_editar:
                col_nome_meta, col_alvo = st.columns(2)
                novo_nome = col_nome_meta.text_input(
                    "Nome", value=meta["nome"], max_chars=100, key=f"meta_nome_{mid}"
                )
                novo_alvo = col_alvo.number_input(
                    "Valor-alvo (R$)", min_value=0.0, step=100.0, format="%.2f",
                    value=meta["valor_alvo"] / 100, key=f"meta_alvo_{mid}",
                )
                col_prazo, col_percentual = st.columns(2)
                novo_prazo = col_prazo.date_input(
                    "Prazo", value=meta["prazo"], format="DD/MM/YYYY", key=f"meta_prazo_{mid}"
                )
                novo_percentual = col_percentual.number_input(
                    "% de cada entrada a separar", min_value=0.0, max_value=100.0, step=1.0,
                    format="%.1f", value=meta["percentual_entrada"], key=f"meta_pct_{mid}",
                )
                if st.button("Salvar alterações", type="primary", key=f"meta_salvar_{mid}"):
                    try:
                        repo.atualizar_meta(
                            mid, novo_nome, reais_para_centavos(novo_alvo), novo_prazo, novo_percentual
                        )
                        manter_aberta(mid)
                        guardar_aviso("Meta atualizada.", "aviso_metas")
                        st.rerun()
                    except ValueError as erro:
                        st.error(str(erro))

                st.divider()
                confirmar = st.checkbox(
                    "Confirmo que quero excluir esta meta e todas as suas contribuições.",
                    key=f"meta_confirmar_{mid}",
                )
                if st.button("Excluir meta", disabled=not confirmar, key=f"meta_excluir_{mid}"):
                    repo.excluir_meta(mid)
                    guardar_aviso("Meta excluída.", "aviso_metas")
                    st.rerun()


with aba_metas:
    mostrar_aviso("aviso_metas")

    saldo = fluxo_caixa.saldo_atual()
    reservado = repo.total_reservado()
    m1, m2, m3 = st.columns(3)
    m1.metric("Saldo atual", formatar_brl(saldo))
    m2.metric("Reservado nas metas", formatar_brl(reservado))
    m3.metric(
        "Livre para gastar", formatar_brl(saldo - reservado),
        help="Saldo atual menos o que já foi separado nas metas. Reservar é um controle do "
             "app: o dinheiro continua na sua conta.",
    )

    metas = repo.listar_metas()
    if not metas:
        st.info("Nenhuma meta criada ainda. Crie a primeira abaixo, por exemplo uma reserva de emergência.")
    for meta in metas:
        cartao_da_meta(meta)

    with st.expander("Nova meta", expanded=not metas):
        with st.form("nova_meta", clear_on_submit=True, border=False):
            col_nome_meta, col_valor_meta = st.columns(2)
            nome_meta = col_nome_meta.text_input(
                "Nome da meta", max_chars=100, placeholder="Ex.: Reserva de emergência"
            )
            with col_valor_meta:
                valor_alvo = campo_valor("Valor-alvo (R$)", passo=100.0) or 0
            col_prazo_meta, col_percentual_meta = st.columns(2)
            prazo_meta = col_prazo_meta.date_input(
                "Prazo (opcional)", value=None, min_value=HOJE, format="DD/MM/YYYY"
            )
            percentual_meta = col_percentual_meta.number_input(
                "% de cada entrada a separar (opcional)", value=None, min_value=0.0,
                max_value=100.0, step=1.0, format="%.1f", placeholder="Ex.: 10",
                help="Se preencher, o app sugere separar esse percentual a cada entrada que você registrar.",
            )
            criar = st.form_submit_button("Criar meta", type="primary")
        if criar:
            if valor_alvo <= 0:
                st.error("Informe um valor-alvo maior que zero.")
            else:
                try:
                    repo.criar_meta(nome_meta, valor_alvo, prazo_meta, percentual_meta or 0)
                    guardar_aviso(f"Meta '{nome_meta.strip()}' criada.", "aviso_metas")
                    st.rerun()
                except ValueError as erro:
                    st.error(str(erro))
