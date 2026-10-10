from collections import Counter
from datetime import date

import pytest

from src.database import repositories as repo
from src.services import importacao
from src.utils.textos import normalizar_texto

HOJE = date(2026, 10, 20)


def _linha(n=2, data="05/10/2026", valor="45,90", tipo="saida", categoria="Mercado",
           descricao="", forma=""):
    return {"linha": n, "data": data, "valor": valor, "tipo": tipo, "categoria": categoria,
            "descricao": descricao, "forma_pagamento": forma}


def _cats(**nomes):
    return [{"id": i, "nome": n, "tipo": t} for i, (n, t) in enumerate(nomes.values(), start=1)]


# ---------- textos ----------
def test_normalizar_texto_ignora_acento_caixa_e_espacos():
    assert normalizar_texto("  Alimentação ") == "alimentacao"
    assert normalizar_texto("CAFÉ") == normalizar_texto("cafe")


# ---------- conversão de campos ----------
def test_converter_valor_aceita_formatos_brasileiros():
    assert importacao.converter_valor("45,90") == 4590
    assert importacao.converter_valor("1.234,56") == 123456
    assert importacao.converter_valor("R$ 10") == 1000
    assert importacao.converter_valor("1234.56") == 123456
    assert importacao.converter_valor("7") == 700
    assert importacao.converter_valor(" 0,5 ") == 50


def test_converter_valor_recusa_ambiguo_negativo_e_lixo():
    with pytest.raises(ValueError, match="ambíguo"):
        importacao.converter_valor("1.234")
    with pytest.raises(ValueError, match="positivo"):
        importacao.converter_valor("-5,00")
    for ruim in ("12,345", "abc", "", "1e5", "1,234,56"):
        with pytest.raises(ValueError):
            importacao.converter_valor(ruim)


def test_converter_data_aceita_varios_formatos():
    esperado = date(2026, 10, 5)
    for texto in ("05/10/2026", "5/10/2026", "2026-10-05", "05-10-2026", "05/10/26"):
        assert importacao.converter_data(texto) == esperado


def test_converter_data_recusa_data_impossivel_ou_vazia():
    for ruim in ("31/02/2026", "", "ontem"):
        with pytest.raises(ValueError, match="Data inválida"):
            importacao.converter_data(ruim)


def test_normalizar_tipo():
    assert importacao.normalizar_tipo("Entrada") == "entrada"
    assert importacao.normalizar_tipo("SAÍDA") == "saida"
    assert importacao.normalizar_tipo("Receita") == "entrada"
    assert importacao.normalizar_tipo("despesa") == "saida"
    with pytest.raises(ValueError, match="Tipo inválido"):
        importacao.normalizar_tipo("transferência")


def test_normalizar_forma_de_pagamento():
    assert importacao.normalizar_forma("PIX") == "pix"
    assert importacao.normalizar_forma("Débito") == "debito"
    assert importacao.normalizar_forma("Cartão de Crédito") == "credito"
    assert importacao.normalizar_forma("") is None
    assert importacao.normalizar_forma("boleto") == "outro"


# ---------- leitura do CSV ----------
def test_ler_csv_com_ponto_e_virgula():
    conteudo = "data;valor;tipo;categoria\n05/10/2026;45,90;saida;Mercado\n".encode()
    [linha] = importacao.ler_csv(conteudo)
    assert linha["valor"] == "45,90" and linha["categoria"] == "Mercado"
    assert linha["descricao"] == "" and linha["forma_pagamento"] == ""  # colunas opcionais


def test_ler_csv_com_virgula_e_valor_entre_aspas():
    conteudo = 'data,valor,tipo,categoria\n05/10/2026,"45,90",saida,Mercado\n'.encode()
    [linha] = importacao.ler_csv(conteudo)
    assert linha["valor"] == "45,90"


def test_ler_csv_com_bom_e_cabecalho_com_acento():
    conteudo = ("﻿Data;Valor;Tipo;Categoria;Descrição;Forma de pagamento\n"
                "05/10/2026;10,00;saida;Mercado;Pão;Pix\n").encode("utf-8")
    [linha] = importacao.ler_csv(conteudo)
    assert linha["descricao"] == "Pão" and linha["forma_pagamento"] == "Pix"


def test_ler_csv_salvo_pelo_excel_em_latin1():
    conteudo = "data;valor;tipo;categoria\n05/10/2026;10,00;saida;Alimentação\n".encode("cp1252")
    [linha] = importacao.ler_csv(conteudo)
    assert linha["categoria"] == "Alimentação"


def test_ler_csv_ignora_linhas_vazias_e_guarda_o_numero_da_linha():
    conteudo = "data;valor;tipo;categoria\n\n05/10/2026;1,00;saida;A\n;;;\n06/10/2026;2,00;saida;B\n".encode()
    linhas = importacao.ler_csv(conteudo)
    assert [l["linha"] for l in linhas] == [3, 5]


def test_ler_csv_sem_colunas_obrigatorias():
    with pytest.raises(ValueError, match="Faltam colunas obrigatórias.*categoria"):
        importacao.ler_csv("data;valor;tipo\n05/10/2026;1,00;saida\n".encode())


def test_ler_csv_vazio_ou_so_cabecalho():
    with pytest.raises(ValueError, match="vazio"):
        importacao.ler_csv(b"  \n")
    with pytest.raises(ValueError, match="sem nenhuma linha"):
        importacao.ler_csv(b"data;valor;tipo;categoria\n")


def test_ler_csv_respeita_o_limite_de_linhas():
    corpo = "05/10/2026;1,00;saida;A\n" * (importacao.MAX_LINHAS + 1)
    with pytest.raises(ValueError, match="mais de"):
        importacao.ler_csv(("data;valor;tipo;categoria\n" + corpo).encode())


def test_modelo_csv_e_valido():
    linhas = importacao.ler_csv(importacao.MODELO_CSV.encode())
    assert len(linhas) == 2
    analisadas = importacao.analisar(linhas, [], criar_categorias=True, hoje=HOJE)
    assert all(not i["erros"] for i in analisadas)


# ---------- análise ----------
def test_analisar_reconhece_categoria_sem_acento_e_caixa():
    categorias = [{"id": 7, "nome": "Alimentação", "tipo": "saida"}]
    [item] = importacao.analisar([_linha(categoria="alimentacao")], categorias, hoje=HOJE)
    assert item["categoria_id"] == 7 and item["categoria"] == "Alimentação"
    assert item["erros"] == [] and item["categoria_nova"] is None


def test_analisar_converte_os_campos():
    [item] = importacao.analisar(
        [_linha(descricao=" Pão ", forma="Pix")], [{"id": 1, "nome": "Mercado", "tipo": "saida"}], hoje=HOJE
    )
    assert item["data"] == date(2026, 10, 5) and item["valor"] == 4590
    assert item["descricao"] == "Pão" and item["forma_pagamento"] == "pix"


def test_analisar_recusa_categoria_de_outro_tipo():
    categorias = [{"id": 1, "nome": "Chronomax", "tipo": "entrada"}]
    [item] = importacao.analisar([_linha(categoria="Chronomax", tipo="saida")], categorias, hoje=HOJE)
    assert "é de entrada, mas a linha é de saída" in item["erros"][0]


def test_analisar_marca_categoria_nova():
    [item] = importacao.analisar([_linha(categoria="Academia")], [], criar_categorias=True, hoje=HOJE)
    assert item["categoria_nova"] == "Academia" and item["categoria_id"] is None
    assert item["erros"] == []


def test_analisar_sem_permissao_para_criar_categorias_vira_erro():
    [item] = importacao.analisar([_linha(categoria="Academia")], [], criar_categorias=False, hoje=HOJE)
    assert "não existe" in item["erros"][0]


def test_analisar_junta_grafias_da_mesma_categoria_nova():
    linhas = [_linha(2, categoria="Café"), _linha(3, categoria="cafe")]
    primeira, segunda = importacao.analisar(linhas, [], hoje=HOJE)
    assert primeira["categoria_nova"] == segunda["categoria_nova"] == "Café"


def test_analisar_categoria_nova_com_tipos_conflitantes():
    linhas = [_linha(2, categoria="Extra", tipo="saida"), _linha(3, categoria="Extra", tipo="entrada")]
    primeira, segunda = importacao.analisar(linhas, [], hoje=HOJE)
    assert primeira["erros"] == []
    assert "entrada e como saída" in segunda["erros"][0]


def test_analisar_data_futura_e_so_aviso():
    [item] = importacao.analisar([_linha(data="25/12/2026")], [], hoje=HOJE)
    assert item["erros"] == [] and len(item["avisos"]) == 1


def test_analisar_acumula_os_erros_de_cada_linha():
    [item] = importacao.analisar([_linha(data="x", valor="abc", tipo="?", categoria="")], [], hoje=HOJE)
    assert len(item["erros"]) == 4


def test_analisar_valor_zero_e_descricao_longa_sao_erros():
    linhas = [_linha(2, valor="0"), _linha(3, descricao="x" * 256)]
    zero, longa = importacao.analisar(linhas, [], hoje=HOJE)
    assert "maior que zero" in zero["erros"][0]
    assert "255" in longa["erros"][0]


def test_marcar_duplicadas_conta_ocorrencias():
    categorias = [{"id": 1, "nome": "Mercado", "tipo": "saida"}]
    analisadas = importacao.analisar([_linha(2), _linha(3)], categorias, hoje=HOJE)
    chave = (date(2026, 10, 5), 4590, "saida", 1, "")
    importacao.marcar_duplicadas(analisadas, Counter({chave: 1}))
    assert [i["duplicada"] for i in analisadas] == [True, False]


# ---------- com banco ----------
def _conta_e_categoria():
    return repo.criar_conta("Carteira", "carteira"), repo.criar_categoria("Mercado", "saida")


def _csv(*linhas):
    return ("data;valor;tipo;categoria;descricao;forma_pagamento\n" + "\n".join(linhas) + "\n").encode()


def test_importar_grava_lancamentos_e_cria_categorias(banco_limpo):
    conta, _ = _conta_e_categoria()
    arquivo = _csv(
        "05/10/2026;45,90;saida;Mercado;Compras;pix",
        "10/10/2026;350,00;entrada;Chronomax;Evento;pix",
        "11/10/2026;20,00;saida;Academia;;",
    )
    analisadas = importacao.analisar_arquivo(arquivo, conta, hoje=HOJE)
    resultado = importacao.importar(analisadas, conta)

    assert resultado == {"transacoes": 3, "categorias_criadas": 2, "ignoradas": 0}
    lancamentos = repo.listar_transacoes(mes="2026-10")
    assert len(lancamentos) == 3
    mercado = next(t for t in lancamentos if t["categoria"] == "Mercado")
    assert mercado["valor"] == 4590 and mercado["descricao"] == "Compras" and mercado["forma_pagamento"] == "pix"
    assert {c["nome"] for c in repo.listar_categorias()} == {"Mercado", "Chronomax", "Academia"}


def test_importar_e_tudo_ou_nada(banco_limpo):
    conta, _ = _conta_e_categoria()
    linhas = [
        {"data": date(2026, 10, 5), "valor": 1000, "tipo": "saida", "categoria_nova": "Nova"},
        {"data": date(2026, 10, 6), "valor": -5, "tipo": "saida", "categoria_nova": "Nova"},
    ]
    with pytest.raises(ValueError):
        repo.inserir_transacoes_em_lote(conta, linhas)

    assert repo.listar_transacoes() == []
    assert [c["nome"] for c in repo.listar_categorias()] == ["Mercado"]  # 'Nova' não ficou


def test_importar_em_conta_inexistente(banco_limpo):
    with pytest.raises(ValueError, match="Conta inexistente"):
        repo.inserir_transacoes_em_lote(999, [])


def test_importar_recusa_arquivo_com_erro(banco_limpo):
    conta, _ = _conta_e_categoria()
    analisadas = importacao.analisar_arquivo(_csv("05/10/2026;abc;saida;Mercado;;"), conta, hoje=HOJE)
    with pytest.raises(ValueError, match="linhas com erro"):
        importacao.importar(analisadas, conta)
    assert repo.listar_transacoes() == []


def test_reimportar_o_mesmo_arquivo_marca_tudo_como_duplicado(banco_limpo):
    conta, _ = _conta_e_categoria()
    arquivo = _csv("05/10/2026;45,90;saida;Mercado;Compras;pix", "06/10/2026;10,00;saida;Mercado;;")
    importacao.importar(importacao.analisar_arquivo(arquivo, conta, hoje=HOJE), conta)

    segunda = importacao.analisar_arquivo(arquivo, conta, hoje=HOJE)
    assert all(i["duplicada"] for i in segunda)
    resultado = importacao.importar(segunda, conta)
    assert resultado == {"transacoes": 0, "categorias_criadas": 0, "ignoradas": 2}
    assert len(repo.listar_transacoes()) == 2


def test_incluir_duplicadas_grava_de_novo(banco_limpo):
    conta, _ = _conta_e_categoria()
    arquivo = _csv("05/10/2026;45,90;saida;Mercado;;")
    importacao.importar(importacao.analisar_arquivo(arquivo, conta, hoje=HOJE), conta)

    analisadas = importacao.analisar_arquivo(arquivo, conta, hoje=HOJE)
    importacao.importar(analisadas, conta, incluir_duplicadas=True)
    assert len(repo.listar_transacoes()) == 2


def test_compras_iguais_no_mesmo_arquivo_sao_todas_importadas(banco_limpo):
    conta, _ = _conta_e_categoria()
    arquivo = _csv("05/10/2026;5,00;saida;Mercado;Café;", "05/10/2026;5,00;saida;Mercado;Café;")
    analisadas = importacao.analisar_arquivo(arquivo, conta, hoje=HOJE)
    assert not any(i["duplicada"] for i in analisadas)
    assert importacao.importar(analisadas, conta)["transacoes"] == 2


def test_duplicadas_so_valem_para_a_mesma_conta(banco_limpo):
    conta, _ = _conta_e_categoria()
    outra = repo.criar_conta("Poupança", "poupanca")
    arquivo = _csv("05/10/2026;45,90;saida;Mercado;;")
    importacao.importar(importacao.analisar_arquivo(arquivo, conta, hoje=HOJE), conta)

    [item] = importacao.analisar_arquivo(arquivo, outra, hoje=HOJE)
    assert item["duplicada"] is False


def test_importar_agrupa_grafias_da_mesma_categoria_nova(banco_limpo):
    conta, _ = _conta_e_categoria()
    arquivo = _csv("05/10/2026;5,00;saida;Café;;", "06/10/2026;6,00;saida;cafe;;")
    resultado = importacao.importar(importacao.analisar_arquivo(arquivo, conta, hoje=HOJE), conta)
    assert resultado["categorias_criadas"] == 1
    assert {c["nome"] for c in repo.listar_categorias()} == {"Mercado", "Café"}
