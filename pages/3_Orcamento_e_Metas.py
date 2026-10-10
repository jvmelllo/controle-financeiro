from datetime import date

import streamlit as st

from src.database import repositories as repo
from src.services import fluxo_caixa, orcamento
from src.services import metas as servico_metas
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

# ---------- 5.2 e 5.3 Metas de reserva ----------
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
        progresso = servico_metas.progresso_da_meta(meta)
        st.markdown(f"**{meta['nome']}**" + (" ✅" if progresso["concluida"] else ""))
        st.progress(
            progresso["percentual"] / 100,
            text=(
                f"{formatar_brl(meta['aportado'])} de {formatar_brl(meta['valor_alvo'])} "
                f"({progresso['percentual']:.0f}%)"
            ),
        )
        detalhes = []
        if meta["prazo"]:
            detalhes.append(f"Prazo: {meta['prazo']:%d/%m/%Y}")
        if progresso["atrasada"]:
            detalhes.append("⚠️ prazo vencido")
        if progresso["por_mes"]:
            detalhes.append(f"para chegar lá: cerca de {formatar_brl(progresso['por_mes'])} por mês")
        if meta["percentual_entrada"] > 0:
            detalhes.append(f"{meta['percentual_entrada']:g}% de cada entrada")
        if detalhes:
            st.caption(" · ".join(detalhes))

    if metas:
        st.divider()
        st.subheader("Registrar aporte")
        with st.form("novo_aporte", clear_on_submit=True):
            meta_aporte = st.selectbox("Meta", metas, format_func=lambda m: m["nome"])
            data_aporte = st.date_input("Data", value=HOJE, format="DD/MM/YYYY")
            valor_aporte = campo_valor("Valor do aporte (R$)") or 0
            registrar = st.form_submit_button("Registrar aporte")
        if registrar:
            if valor_aporte <= 0:
                st.error("Informe um valor maior que zero.")
            else:
                try:
                    repo.inserir_aporte(meta_aporte["id"], data_aporte, valor_aporte)
                    guardar_aviso(
                        f"Aporte de {formatar_brl(valor_aporte)} em {meta_aporte['nome']} registrado.",
                        "aviso_metas",
                    )
                    st.rerun()
                except ValueError as erro:
                    st.error(str(erro))

        with st.expander("Ver ou excluir aportes"):
            meta_historico = st.selectbox(
                "Meta", metas, format_func=lambda m: m["nome"], key="meta_historico"
            )
            aportes = repo.listar_aportes(meta_historico["id"])
            if not aportes:
                st.caption("Nenhum aporte ainda.")
            for aporte in aportes[:20]:
                col_data, col_valor, col_acao = st.columns([2, 2, 1])
                col_data.write(f"{aporte['data']:%d/%m/%Y}")
                col_valor.write(formatar_brl(aporte["valor"]))
                if col_acao.button("Excluir", key=f"excluir_aporte_{aporte['id']}"):
                    repo.excluir_aporte(aporte["id"])
                    guardar_aviso("Aporte excluído.", "aviso_metas")
                    st.rerun()
            if len(aportes) > 20:
                st.caption(f"Mostrando os 20 mais recentes de {len(aportes)}.")

    st.divider()
    st.subheader("Nova meta")
    with st.form("nova_meta", clear_on_submit=True):
        nome_meta = st.text_input("Nome da meta", max_chars=100, placeholder="Ex.: Reserva de emergência")
        valor_alvo = campo_valor("Valor-alvo (R$)", passo=100.0) or 0
        prazo_meta = st.date_input(
            "Prazo (opcional)", value=None, min_value=HOJE, format="DD/MM/YYYY"
        )
        percentual_meta = st.number_input(
            "% de cada entrada a separar (opcional)", value=None, min_value=0.0, max_value=100.0,
            step=1.0, format="%.1f", placeholder="Ex.: 10",
        )
        criar = st.form_submit_button("Criar meta")
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

    if metas:
        with st.expander("Editar ou excluir meta"):
            meta_edicao = st.selectbox(
                "Meta", metas, format_func=lambda m: m["nome"], key="meta_edicao"
            )
            mid = meta_edicao["id"]
            novo_nome = st.text_input(
                "Nome", value=meta_edicao["nome"], max_chars=100, key=f"meta_nome_{mid}"
            )
            novo_alvo = st.number_input(
                "Valor-alvo (R$)", min_value=0.0, step=100.0, format="%.2f",
                value=meta_edicao["valor_alvo"] / 100, key=f"meta_alvo_{mid}",
            )
            novo_prazo = st.date_input(
                "Prazo", value=meta_edicao["prazo"], format="DD/MM/YYYY", key=f"meta_prazo_{mid}"
            )
            novo_percentual = st.number_input(
                "% de cada entrada a separar", min_value=0.0, max_value=100.0, step=1.0,
                format="%.1f", value=meta_edicao["percentual_entrada"], key=f"meta_pct_{mid}",
            )
            if st.button("Salvar alterações da meta", key=f"meta_salvar_{mid}"):
                try:
                    repo.atualizar_meta(
                        mid, novo_nome, reais_para_centavos(novo_alvo), novo_prazo, novo_percentual
                    )
                    guardar_aviso("Meta atualizada.", "aviso_metas")
                    st.rerun()
                except ValueError as erro:
                    st.error(str(erro))

            st.divider()
            confirmar = st.checkbox(
                "Confirmo que quero excluir esta meta e todos os seus aportes.",
                key=f"meta_confirmar_{mid}",
            )
            if st.button("Excluir meta", disabled=not confirmar, key=f"meta_excluir_{mid}"):
                repo.excluir_meta(mid)
                guardar_aviso("Meta excluída.", "aviso_metas")
                st.rerun()