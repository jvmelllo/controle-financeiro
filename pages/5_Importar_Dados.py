import pandas as pd
import streamlit as st

from src.database import repositories as repo
from src.services import importacao
from src.utils.avisos import guardar_aviso, mostrar_aviso
from src.utils.componentes import aviso_modo_demo
from src.utils.configuracao import ler
from src.utils.dinheiro import formatar_brl

st.set_page_config(page_title="Importar dados", page_icon="📥", layout="wide")
st.title("Importar dados")
st.caption(
    "Traga lançamentos de uma planilha (CSV). A importação é tudo ou nada: "
    "se algo falhar, nada é gravado."
)
aviso_modo_demo()

mostrar_aviso()

banco = ler("DB_NAME", "?")
eh_demo = banco.endswith("_demo")
if eh_demo:
    st.info(f"Banco em uso: **{banco}** (dados de demonstração).")
else:
    st.warning(f"Banco em uso: **{banco}**. Os lançamentos importados serão gravados neste banco.")

ROTULO_TIPO = {"entrada": "Entrada", "saida": "Saída"}

# ---------- 1. Modelo ----------
st.subheader("1. Modelo do arquivo")
st.download_button(
    "Baixar modelo (CSV)",
    importacao.MODELO_CSV.encode("utf-8-sig"),
    file_name="modelo_importacao.csv",
    mime="text/csv",
)
with st.expander("Regras das colunas"):
    st.markdown(
        """
- **data**: dd/mm/aaaa (também aceita aaaa-mm-dd).
- **valor**: em reais, sempre positivo, com vírgula nos centavos (ex.: 45,90 ou 1.234,56).
- **tipo**: `entrada` ou `saida`. Quem diz se o dinheiro entrou ou saiu é esta coluna.
- **categoria**: nome da categoria. Se não existir, pode ser criada automaticamente.
- **descricao** (opcional): até 255 caracteres.
- **forma_pagamento** (opcional): pix, debito, credito, dinheiro ou outro.

O arquivo pode usar `;` ou `,` como separador. Até 5.000 linhas por arquivo.
"""
    )

# ---------- 2. Arquivo ----------
st.subheader("2. Enviar o arquivo")
contas = repo.listar_contas()
if not contas:
    st.info("Crie uma conta na página Cadastros antes de importar.")
    st.stop()

conta = st.selectbox("Conta de destino", contas, format_func=lambda c: c["nome"])
criar_categorias = st.checkbox("Criar automaticamente as categorias que ainda não existem", value=True)
arquivo = st.file_uploader("Arquivo CSV", type=["csv"])
if arquivo is None:
    st.stop()

try:
    analisadas = importacao.analisar_arquivo(arquivo.getvalue(), conta["id"], criar_categorias)
except ValueError as erro:
    st.error(str(erro))
    st.stop()

# ---------- 3. Conferência ----------
st.subheader("3. Conferir e importar")
com_erro = [i for i in analisadas if i["erros"]]
duplicadas = [i for i in analisadas if i["duplicada"]]
categorias_novas = {i["categoria_nova"] for i in analisadas if i["categoria_nova"]}

c1, c2, c3, c4 = st.columns(4)
c1.metric("Linhas lidas", len(analisadas))
c2.metric("Com erro", len(com_erro))
c3.metric("Já existem", len(duplicadas))
c4.metric("Categorias novas", len(categorias_novas))


def situacao(item: dict) -> str:
    if item["erros"]:
        return "❌ " + " ".join(item["erros"])
    if item["duplicada"]:
        return "Já existe na conta (será ignorada)"
    texto = "Cria a categoria" if item["categoria_nova"] else "OK"
    if item["avisos"]:
        texto += " ⚠️ " + " ".join(item["avisos"])
    return texto


tabela = pd.DataFrame(
    [
        {
            "Linha": i["linha"],
            "Data": f"{i['data']:%d/%m/%Y}" if i["data"] else "—",
            "Tipo": ROTULO_TIPO.get(i["tipo"], "—"),
            "Categoria": i["categoria"] or "—",
            "Valor": formatar_brl(i["valor"]) if i["valor"] is not None else "—",
            "Descrição": i["descricao"] or "",
            "Situação": situacao(i),
        }
        for i in analisadas
    ]
)
st.dataframe(tabela, hide_index=True)

if com_erro:
    st.error(
        "Corrija as linhas com erro no arquivo e envie de novo. "
        "Nada é importado enquanto houver erro."
    )

incluir_duplicadas = False
if duplicadas:
    incluir_duplicadas = st.checkbox(
        f"Importar também as {len(duplicadas)} linha(s) que já existem",
        help="Só marque se esses lançamentos realmente se repetem.",
    )

confirmado = True
if not eh_demo:
    confirmado = st.checkbox(f"Confirmo que quero importar no banco real ({banco}).")

a_importar = len(analisadas) - (0 if incluir_duplicadas else len(duplicadas))
pode_importar = not com_erro and a_importar > 0 and confirmado

if st.button("Importar", type="primary", disabled=not pode_importar):
    try:
        resultado = importacao.importar(analisadas, conta["id"], incluir_duplicadas)
    except ValueError as erro:
        st.error(str(erro))
    else:
        texto = f"{resultado['transacoes']} lançamento(s) importado(s)"
        if resultado["categorias_criadas"]:
            texto += f", {resultado['categorias_criadas']} categoria(s) criada(s)"
        if resultado["ignoradas"]:
            texto += f", {resultado['ignoradas']} ignorada(s) por já existirem"
        guardar_aviso(texto + ".")
        st.rerun()
