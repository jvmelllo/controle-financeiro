from datetime import date

import streamlit as st

from src.assistant import ia, modelos, regras
from src.assistant.alertas import gerar_alertas
from src.assistant.contexto import montar_contexto
from src.utils.alertas_ui import exibir_alerta
from src.utils.dinheiro import escapar_markdown

LIMITE_PERGUNTAS_POR_SESSAO = 20  # a conversa longa deixa o modelo local lento e confuso
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
    st.success("Tudo certo por aqui: nenhum alerta para este mês.")
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

# ---------- Conversa com a IA local (Ollama) ----------
st.divider()
st.subheader("Converse com o assistente")
st.caption(
    "O chat usa o Ollama, que roda no seu computador: nada sai da sua máquina e não há custo. "
    "É opcional; os alertas acima funcionam sem ele."
)

diagnostico = ia.diagnosticar()

if diagnostico.estado != "pronto":
    if diagnostico.estado == "offline":
        st.info(
            "Não encontrei o Ollama. Se ainda não instalou, instale (PowerShell) e abra o aplicativo; "
            "se já instalou, abra o aplicativo Ollama e clique em Verificar de novo."
        )
        st.code("winget install Ollama.Ollama", language="powershell")
    else:
        st.info("O Ollama está aberto, mas ainda não há nenhum modelo baixado.")

    ram = modelos.memoria_ram_gb()
    sugerido = modelos.recomendar(ram)
    st.markdown(
        f"Para o seu computador{f' (cerca de {ram:.0f} GB de RAM)' if ram else ''}, "
        f"o modelo indicado é o **{sugerido.nome}** (download de cerca de {sugerido.download_gb:g} GB):"
    )
    st.code(modelos.comando_de_instalacao(sugerido.nome), language="powershell")
    with st.expander("Outros modelos"):
        for m in modelos.CATALOGO:
            st.markdown(
                f"- **{m.nome}** (cerca de {m.download_gb:g} GB, a partir de {m.ram_minima_gb} GB de RAM): "
                f"{m.descricao}"
            )
        st.caption(
            "Para usar outro modelo como padrão, coloque `OLLAMA_MODELO=nome` no arquivo .env "
            "e reinicie o app."
        )
    st.button("Verificar de novo")
    st.stop()

nomes = [m.nome for m in diagnostico.modelos]
modelo = st.selectbox(
    "Modelo",
    nomes,
    index=nomes.index(diagnostico.modelo_escolhido),
    help="Modelos maiores respondem melhor, mas demoram mais. A primeira pergunta é a mais lenta, "
    "porque o modelo precisa ser carregado na memória.",
)

contexto = montar_contexto(hoje)
with st.expander("O que a IA recebe"):
    st.caption(
        "Só totais e nomes de categorias e metas, e só para o modelo no seu computador. "
        "Descrições dos lançamentos e nomes de contas nunca são enviados."
    )
    st.code(contexto, language=None)

historico = st.session_state.setdefault("chat_ia", [])
perguntas_feitas = sum(m["role"] == "user" for m in historico)

colunas = st.columns(len(SUGESTOES))
pergunta = None
for coluna, sugestao in zip(colunas, SUGESTOES):
    if coluna.button(sugestao):
        pergunta = sugestao

for mensagem in historico:
    with st.chat_message(mensagem["role"]):
        st.markdown(escapar_markdown(mensagem["content"]))
        if mensagem.get("aviso"):
            st.caption(mensagem["aviso"])

digitada = st.chat_input("Pergunte algo sobre as suas finanças")
pergunta = digitada or pergunta


def aviso_de_numeros(resposta: str) -> str | None:
    fora = ia.verificar_numeros(resposta, contexto)
    if not fora:
        return None
    return escapar_markdown(
        f"Confira: {', '.join(fora)} não aparece(m) no resumo enviado. "
        "Modelos locais podem errar contas; use os números do painel como referência."
    )


if pergunta:
    if perguntas_feitas >= LIMITE_PERGUNTAS_POR_SESSAO:
        st.warning(
            f"Limite de {LIMITE_PERGUNTAS_POR_SESSAO} perguntas por conversa atingido. "
            "Clique em 'Limpar conversa' para recomeçar."
        )
    else:
        with st.chat_message("user"):
            st.markdown(escapar_markdown(pergunta))
        partes: list[str] = []

        def resposta_em_fluxo():
            for trecho in ia.perguntar_em_fluxo(pergunta, historico, contexto, modelo=modelo):
                espera.empty()  # apaga o "Pensando..." quando o primeiro trecho chega
                partes.append(trecho)
                yield escapar_markdown(trecho)  # o '$' de "R$" viraria fórmula matemática

        try:
            with st.chat_message("assistant"):
                espera = st.empty()
                espera.caption("Pensando... a primeira resposta pode demorar enquanto o modelo carrega.")
                st.write_stream(resposta_em_fluxo())
                resposta = "".join(partes).strip()
                aviso = aviso_de_numeros(resposta)
                if aviso:
                    st.caption(aviso)
        except ValueError as erro:
            st.warning(str(erro))
        except ia.IAIndisponivel as erro:
            st.error(str(erro))
        else:
            historico.append({"role": "user", "content": pergunta.strip()})
            historico.append({"role": "assistant", "content": resposta, "aviso": aviso})

if historico:
    if st.button("Limpar conversa"):
        st.session_state["chat_ia"] = []
        st.rerun()
    feitas = sum(m["role"] == "user" for m in historico)
    st.caption(f"{feitas} de {LIMITE_PERGUNTAS_POR_SESSAO} perguntas nesta conversa.")
