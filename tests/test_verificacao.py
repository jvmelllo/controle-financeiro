from src.assistant.verificacao import valores_em_centavos, valores_fora_dos_dados


def test_valores_em_varios_formatos():
    texto = "Gastou R$ 1.234,56 e R$80 e R$ 7,5 e R$ 2.000 ou R$ 10,05."
    assert valores_em_centavos(texto) == [123456, 8000, 750, 200000, 1005]


def test_texto_sem_valores():
    assert valores_em_centavos("Nada de dinheiro aqui, só 20% e 3 dias.") == []


def test_valor_que_esta_nos_dados_nao_e_apontado():
    contexto = "- Saldo atual: R$ 6.880,00\n- Lazer: R$ 120,00"
    assert valores_fora_dos_dados("Seu saldo é R$ 6.880,00 e Lazer R$ 120,00.", contexto) == []


def test_valor_inventado_e_apontado_uma_vez_so():
    contexto = "- Lazer: R$ 120,00"
    resposta = "Você gastou R$ 999,90 em Lazer, ou seja, R$ 999,90 no total e R$ 120,00 antes."
    assert valores_fora_dos_dados(resposta, contexto) == ["R$ 999,90"]


def test_mesmo_valor_com_ou_sem_centavos_e_igual():
    assert valores_fora_dos_dados("R$ 120", "Lazer: R$ 120,00") == []
