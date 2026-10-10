"""Importação de lançamentos a partir de um arquivo CSV.

Fluxo: ler_csv -> analisar (valida cada linha) -> marcar_duplicadas -> importar (tudo ou nada).
Tudo, exceto contar_existentes e importar, funciona sem banco.
"""

import csv
import io
import re
from collections import Counter
from datetime import date, datetime

from src.database import repositories as repo
from src.services.validacoes import validar_lancamento
from src.utils.dinheiro import reais_para_centavos
from src.utils.textos import normalizar_texto

COLUNAS = ["data", "valor", "tipo", "categoria", "descricao", "forma_pagamento"]
OBRIGATORIAS = ["data", "valor", "tipo", "categoria"]
MAX_LINHAS = 5000
TAMANHO_DESCRICAO = 255

MODELO_CSV = (
    "data;valor;tipo;categoria;descricao;forma_pagamento\n"
    "05/10/2026;45,90;saida;Alimentação;Mercado;pix\n"
    "10/10/2026;350,00;entrada;Chronomax;Evento esportivo;pix\n"
)

_ALIAS_COLUNAS = {
    "data": "data",
    "valor": "valor",
    "tipo": "tipo",
    "categoria": "categoria",
    "descricao": "descricao",
    "forma_pagamento": "forma_pagamento",
    "forma de pagamento": "forma_pagamento",
    "forma": "forma_pagamento",
    "pagamento": "forma_pagamento",
}
_TIPOS = {
    "entrada": "entrada", "receita": "entrada",
    "saida": "saida", "despesa": "saida", "gasto": "saida",
}
_FORMAS = {
    "pix": "pix", "debito": "debito", "credito": "credito", "dinheiro": "dinheiro", "outro": "outro",
    "cartao de credito": "credito", "cartao credito": "credito",
    "cartao de debito": "debito", "cartao debito": "debito",
}
_ROTULO_TIPO = {"entrada": "entrada", "saida": "saída"}


# ---------- leitura do arquivo ----------
def decodificar(conteudo: bytes) -> str:
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252")  # CSV salvo pelo Excel no Windows


def ler_csv(conteudo: bytes) -> list[dict]:
    """Lê o CSV e devolve uma lista de linhas ({'linha': n, 'data': ..., ...}), com os textos crus."""
    texto = decodificar(conteudo)
    primeira = next((l for l in texto.splitlines() if l.strip()), "")
    if not primeira:
        raise ValueError("O arquivo está vazio.")
    delimitador = max(";,\t", key=primeira.count)

    leitor = csv.reader(io.StringIO(texto), delimiter=delimitador)
    cabecalho = None
    linhas = []
    for campos in leitor:
        if not any(c.strip() for c in campos):
            continue
        if cabecalho is None:
            cabecalho = [_ALIAS_COLUNAS.get(normalizar_texto(c)) for c in campos]
            faltando = [c for c in OBRIGATORIAS if c not in cabecalho]
            if faltando:
                raise ValueError(
                    f"Faltam colunas obrigatórias no arquivo: {', '.join(faltando)}. "
                    f"Use o modelo (colunas: {', '.join(COLUNAS)})."
                )
            continue
        if len(linhas) >= MAX_LINHAS:
            raise ValueError(f"O arquivo tem mais de {MAX_LINHAS} linhas. Divida em arquivos menores.")
        linha = {"linha": leitor.line_num}
        for nome, valor in zip(cabecalho, campos):
            if nome:
                linha[nome] = valor.strip()
        for coluna in COLUNAS:
            linha.setdefault(coluna, "")
        linhas.append(linha)

    if not linhas:
        raise ValueError("O arquivo só tem o cabeçalho, sem nenhuma linha de dados.")
    return linhas


# ---------- conversão de cada campo ----------
def converter_data(texto: str) -> date:
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texto.strip(), formato).date()
        except ValueError:
            continue
    raise ValueError(f"Data inválida: {texto!r}. Use dd/mm/aaaa.")


def converter_valor(texto: str) -> int:
    """'1.234,56' -> 123456 (centavos). Sempre positivo: a coluna 'tipo' diz se entrou ou saiu."""
    bruto = str(texto).strip().replace("R$", "").replace(" ", "")
    if not bruto:
        raise ValueError("Valor vazio.")
    if bruto.startswith("-"):
        raise ValueError(f"Use valor positivo ({texto!r}): a coluna 'tipo' diz se é entrada ou saída.")
    if "," in bruto:
        normal = bruto.replace(".", "").replace(",", ".")
    else:
        normal = bruto
        if "." in bruto and len(bruto.rsplit(".", 1)[1]) == 3:
            raise ValueError(f"Valor ambíguo ({texto!r}). Use vírgula para os centavos, como 1.234,00.")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", normal):
        raise ValueError(f"Valor inválido: {texto!r}. Use números com até 2 casas decimais, como 45,90.")
    return reais_para_centavos(normal)


def normalizar_tipo(texto: str) -> str:
    tipo = _TIPOS.get(normalizar_texto(texto))
    if tipo is None:
        raise ValueError(f"Tipo inválido: {texto!r}. Use 'entrada' ou 'saida'.")
    return tipo


def normalizar_forma(texto: str) -> str | None:
    chave = normalizar_texto(texto)
    if not chave:
        return None
    return _FORMAS.get(chave, "outro")


# ---------- análise das linhas ----------
def analisar(
    linhas: list[dict], categorias: list[dict], criar_categorias: bool = True, hoje: date | None = None
) -> list[dict]:
    """Valida cada linha e a casa com as categorias existentes. Não grava nada."""
    por_nome = {normalizar_texto(c["nome"]): c for c in categorias}
    novas: dict[str, dict] = {}
    resultado = []

    for linha in linhas:
        erros: list[str] = []
        avisos: list[str] = []
        item = {
            "linha": linha["linha"], "data": None, "valor": None, "tipo": None,
            "categoria": linha["categoria"].strip(), "categoria_id": None, "categoria_nova": None,
            "descricao": None, "forma_pagamento": None, "duplicada": False,
            "erros": erros, "avisos": avisos,
        }

        for campo, conversor in (("data", converter_data), ("valor", converter_valor), ("tipo", normalizar_tipo)):
            try:
                item[campo] = conversor(linha[campo])
            except ValueError as erro:
                erros.append(str(erro))

        if item["data"] is not None and item["valor"] is not None:
            erros_v, avisos_v = validar_lancamento(item["data"], item["valor"], hoje)
            erros += erros_v
            avisos += avisos_v

        descricao = linha["descricao"].strip()
        if len(descricao) > TAMANHO_DESCRICAO:
            erros.append(f"Descrição com mais de {TAMANHO_DESCRICAO} caracteres.")
        else:
            item["descricao"] = descricao or None
        item["forma_pagamento"] = normalizar_forma(linha["forma_pagamento"])

        nome = item["categoria"]
        if not nome:
            erros.append("Categoria vazia.")
        else:
            chave = normalizar_texto(nome)
            existente = por_nome.get(chave)
            if existente:
                item["categoria_id"] = existente["id"]
                item["categoria"] = existente["nome"]
                if item["tipo"] and existente["tipo"] != item["tipo"]:
                    erros.append(
                        f"A categoria '{existente['nome']}' é de {_ROTULO_TIPO[existente['tipo']]}, "
                        f"mas a linha é de {_ROTULO_TIPO[item['tipo']]}."
                    )
            elif not criar_categorias:
                erros.append(
                    f"A categoria '{nome}' não existe. Crie em Cadastros ou marque a opção "
                    "de criar categorias automaticamente."
                )
            elif item["tipo"]:
                nova = novas.setdefault(chave, {"nome": nome, "tipo": item["tipo"]})
                if nova["tipo"] != item["tipo"]:
                    erros.append(
                        f"A categoria nova '{nova['nome']}' aparece como entrada e como saída no arquivo."
                    )
                else:
                    item["categoria_nova"] = nova["nome"]
                    item["categoria"] = nova["nome"]

        resultado.append(item)
    return resultado


def _chave(data, valor, tipo, categoria_id, descricao) -> tuple:
    return (data, valor, tipo, categoria_id, descricao or "")


def contar_existentes(analisadas: list[dict], conta_id: int) -> Counter:
    """Quantos lançamentos iguais já existem na conta, nos meses que o arquivo cobre."""
    meses = {f"{i['data']:%Y-%m}" for i in analisadas if i["data"] is not None}
    existentes: Counter = Counter()
    for mes in sorted(meses):
        for t in repo.listar_transacoes(mes=mes, conta_id=conta_id):
            existentes[_chave(t["data"], t["valor"], t["tipo"], t["categoria_id"], t["descricao"])] += 1
    return existentes


def marcar_duplicadas(analisadas: list[dict], existentes: Counter) -> None:
    """Marca como duplicada a linha que já existe no banco.

    Conta ocorrências: se o banco tem 1 lançamento igual e o arquivo tem 2, só o primeiro
    é duplicado (duas compras iguais no mesmo dia são normais).
    """
    restantes = Counter(existentes)
    for item in analisadas:
        if item["erros"] or item["categoria_id"] is None:
            continue
        chave = _chave(item["data"], item["valor"], item["tipo"], item["categoria_id"], item["descricao"])
        if restantes[chave] > 0:
            restantes[chave] -= 1
            item["duplicada"] = True


def analisar_arquivo(
    conteudo: bytes, conta_id: int, criar_categorias: bool = True, hoje: date | None = None
) -> list[dict]:
    linhas = ler_csv(conteudo)
    analisadas = analisar(linhas, repo.listar_categorias(apenas_ativas=False), criar_categorias, hoje)
    marcar_duplicadas(analisadas, contar_existentes(analisadas, conta_id))
    return analisadas


# ---------- gravação ----------
def importar(analisadas: list[dict], conta_id: int, incluir_duplicadas: bool = False) -> dict:
    """Grava as linhas (tudo ou nada). Recusa arquivos com linhas inválidas."""
    if any(i["erros"] for i in analisadas):
        raise ValueError("O arquivo tem linhas com erro. Corrija e envie de novo.")

    selecionadas = [i for i in analisadas if incluir_duplicadas or not i["duplicada"]]
    ignoradas = len(analisadas) - len(selecionadas)
    if not selecionadas:
        return {"transacoes": 0, "categorias_criadas": 0, "ignoradas": ignoradas}

    resultado = repo.inserir_transacoes_em_lote(
        conta_id,
        [
            {
                "data": i["data"], "valor": i["valor"], "tipo": i["tipo"],
                "descricao": i["descricao"], "forma_pagamento": i["forma_pagamento"],
                "categoria_id": i["categoria_id"], "categoria_nova": i["categoria_nova"],
            }
            for i in selecionadas
        ],
    )
    return {**resultado, "ignoradas": ignoradas}
