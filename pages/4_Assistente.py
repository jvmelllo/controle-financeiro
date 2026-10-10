from datetime import date

import streamlit as st

from src.assistant import ia, regras
from src.assistant.alertas import gerar_alertas
from src.assistant.contexto import montar_contexto
from src.utils.alertas_ui import exibir_alerta
from src.utils.dinheiro import escapar_markdown

LIMITE_PERGUNTAS_POR_SESSAO = 20  # trava simples de custo: reiniciar a página zera a contagem
SUGESTOES = [
    "Onde estou gastando mais este mês?",
    "Consigo fechar o mês no azul?",
    "O que posso cortar para sobrar mais?",
]

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
    st.write("Os alertas acima seguem regras fixas e transparentes, sem inteligência artificial:")
    for descricao in regras.descricao_das_regras():
        st.markdown(f"- {descricao}")
    st.caption(
        "Os limites (como 80% do orçamento ou 20% acima da média) ficam no topo do arquivo "
        "src/assistant/regras.py e podem ser ajustados."
    )

# ---------- Conversa com a IA (opcional) ----------
st.divider()
st.subheader("💬 Converse com o assistente")

if not ia.chave_configurada():
    st.info(
        "O chat usa inteligência artificial e é opcional. Para ativar, coloque sua chave da API "
        "no arquivo .env (linha `ANTHROPIC_API_KEY=...`) e reinicie o app. "
        "Os alertas acima funcionam sem isso."
    )
    st.stop()

permitido = st.toggle(
    "Permitir enviar um resumo dos meus números para a IA",
    key="ia_permitida",
    help="Sem isso nada sai do seu computador. Com isso, só o resumo abaixo é enviado a cada pergunta.",
)
contexto = montar_contexto(hoje)
with st.expander("O que a IA recebe"):
    st.caption(
        "Só totais e nomes de categorias e metas. Descrições dos lançamentos e nomes de contas "
        "nunca são enviados."
    )
    st.code(contexto, language=None)

historico = st.session_state.setdefault("chat_ia", [])
perguntas_feitas = sum(m["role"] == "user" for m in historico)

colunas = st.columns(len(SUGESTOES))
pergunta = None
for coluna, sugestao in zip(colunas, SUGESTOES):
    if coluna.button(sugestao, disabled=not permitido):
        pergunta = sugestao

for mensagem in historico:
    with st.chat_message(mensagem["role"]):
        st.markdown(escapar_markdown(mensagem["content"]))

digitada = st.chat_input("Pergunte algo sobre as suas finanças", disabled=not permitido)
pergunta = digitada or pergunta

if pergunta:
    if perguntas_feitas >= LIMITE_PERGUNTAS_POR_SESSAO:
        st.warning(
            f"Limite de {LIMITE_PERGUNTAS_POR_SESSAO} perguntas por conversa atingido. "
            "Clique em 'Limpar conversa' para recomeçar."
        )
    else:
        with st.chat_message("user"):
            st.markdown(escapar_markdown(pergunta))
        try:
            with st.spinner("Pensando..."):
                resposta = ia.perguntar(pergunta, historico, contexto)
        except ValueError as erro:
            st.warning(str(erro))
        except ia.IAIndisponivel as erro:
            st.error(str(erro))
        else:
            with st.chat_message("assistant"):
                st.markdown(escapar_markdown(resposta))
            historico.append({"role": "user", "content": pergunta.strip()})
            historico.append({"role": "assistant", "content": resposta})

if historico:
    if st.button("Limpar conversa"):
        st.session_state["chat_ia"] = []
        st.rerun()
    feitas = sum(m["role"] == "user" for m in historico)
    st.caption(f"{feitas} de {LIMITE_PERGUNTAS_POR_SESSAO} perguntas nesta conversa.")