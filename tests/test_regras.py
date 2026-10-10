from dataclasses import FrozenInstanceError

import pytest

from src.assistant import regras
from src.assistant.regras import Alerta


def _item(situacao, percentual, gasto, limite, categoria="Lazer", categoria_id=1):
    return {
        "categoria_id": categoria_id,
        "categoria": categoria,
        "limite": limite,
        "gasto": gasto,
        "restante": limite - gasto,
        "percentual": percentual,
        "situacao": situacao,
    }


def _meta(valor_alvo=340000, aportado=0, aportado_no_mes=0, percentual=10, meta_id=1):
    return {
        "id": meta_id,
        "nome": "Reserva",
        "valor_alvo": valor_alvo,
        "aportado": aportado,
        "aportado_no_mes": aportado_no_mes,
        "percentual_entrada": percentual,
    }


# ---------- orçamento por categoria ----------
def test_orcamento_ok_nao_gera_alerta():
    assert regras.alertas_de_orcamento([_item("ok", 50, 5000, 10000)], 10) == []


def test_orcamento_em_atencao_sugere_valor_por_dia():
    [alerta] = regras.alertas_de_orcamento([_item("atencao", 85, 8500, 10000)], 10)
    assert alerta.nivel == "atencao"
    assert alerta.codigo == "orcamento_atencao_1"
    assert "Lazer" in alerta.titulo and "85%" in alerta.titulo
    assert "R$ 15,00" in alerta.sugestao  # restam 1500 centavos
    assert "R$ 1,50 por dia" in alerta.sugestao  # 1500 / 10 dias


def test_orcamento_em_atencao_no_ultimo_dia_do_mes():
    [alerta] = regras.alertas_de_orcamento([_item("atencao", 90, 9000, 10000)], 0)
    assert "último dia" in alerta.sugestao


def test_orcamento_estourado_e_critico_e_mostra_o_excesso():
    [alerta] = regras.alertas_de_orcamento([_item("estourado", 120, 12000, 10000)], 10)
    assert alerta.nivel == "critico"
    assert alerta.codigo == "orcamento_estourado_1"
    assert "R$ 20,00 acima" in alerta.mensagem


def test_orcamento_gera_um_alerta_por_categoria_fora_do_ok():
    itens = [
        _item("ok", 10, 1000, 10000, "Mercado", 1),
        _item("atencao", 85, 8500, 10000, "Lazer", 2),
        _item("estourado", 130, 13000, 10000, "Transporte", 3),
    ]
    alertas = regras.alertas_de_orcamento(itens, 10)
    assert [a.codigo for a in alertas] == ["orcamento_atencao_2", "orcamento_estourado_3"]


# ---------- sem orçamento ----------
def test_sem_orcamento_com_gastos_sugere_criar_limites():
    alerta = regras.alerta_sem_orcamento(False, 5000)
    assert alerta.codigo == "sem_orcamento"
    assert alerta.nivel == "info"


def test_sem_orcamento_nao_alerta_com_limites_ou_sem_gastos():
    assert regras.alerta_sem_orcamento(True, 5000) is None
    assert regras.alerta_sem_orcamento(False, 0) is None


# ---------- gasto acima da média ----------
def test_media_dentro_do_esperado_nao_alerta():
    # média 100000/mês; no dia 15 de 30 o esperado é 50000; 55000 é +10%
    assert regras.alerta_gasto_acima_da_media(55000, [100000] * 3, 15, 30) is None


def test_media_20_por_cento_acima_gera_atencao():
    alerta = regras.alerta_gasto_acima_da_media(62000, [100000] * 3, 15, 30)  # +24%
    assert alerta.codigo == "gasto_acima_da_media"
    assert alerta.nivel == "atencao"
    assert "24%" in alerta.mensagem


def test_media_50_por_cento_acima_gera_critico():
    alerta = regras.alerta_gasto_acima_da_media(80000, [100000] * 3, 15, 30)  # +60%
    assert alerta.nivel == "critico"


def test_media_nao_roda_no_comeco_do_mes():
    assert regras.alerta_gasto_acima_da_media(90000, [100000] * 3, 4, 30) is None


def test_media_sem_historico_nao_alerta():
    assert regras.alerta_gasto_acima_da_media(90000, [], 15, 30) is None
    assert regras.alerta_gasto_acima_da_media(90000, [0, 0], 15, 30) is None


# ---------- ritmo de gastos e saldo livre ----------
def test_saldo_livre_negativo_e_critico():
    alerta = regras.alerta_ritmo_de_gastos(-1000, 0, 10, 30)
    assert alerta.codigo == "saldo_esgotado"
    assert alerta.nivel == "critico"


def test_saldo_livre_zerado_com_gastos_e_critico():
    assert regras.alerta_ritmo_de_gastos(0, 5000, 10, 30).codigo == "saldo_esgotado"


def test_saldo_zerado_sem_nenhum_movimento_nao_alerta():
    assert regras.alerta_ritmo_de_gastos(0, 0, 10, 30) is None


def test_saldo_dura_ate_o_fim_do_mes_nao_alerta():
    # ritmo de 3000/dia; 100000 duram 33 dias e faltam 20
    assert regras.alerta_ritmo_de_gastos(100000, 30000, 10, 30) is None


def test_saldo_que_nao_dura_gera_atencao_com_limite_diario():
    # ritmo de 3000/dia; 30000 duram 10 dias, mas faltam 20 -> 1500/dia
    alerta = regras.alerta_ritmo_de_gastos(30000, 30000, 10, 30)
    assert alerta.codigo == "ritmo_de_gastos"
    assert alerta.nivel == "atencao"
    assert "10 dia(s)" in alerta.mensagem
    assert "R$ 15,00 por dia" in alerta.sugestao


def test_ritmo_nao_roda_no_comeco_do_mes():
    assert regras.alerta_ritmo_de_gastos(1000, 30000, 3, 30) is None


def test_ritmo_nao_alerta_no_ultimo_dia_do_mes():
    assert regras.alerta_ritmo_de_gastos(1000, 30000, 30, 30) is None


# ---------- reserva do mês ----------
def test_reserva_pendente_sugere_o_valor_que_falta():
    # entrou R$ 2.000,00; 10% = R$ 200,00 e nada foi reservado
    [alerta] = regras.alertas_de_reserva(200000, [_meta()])
    assert alerta.codigo == "reserva_pendente_1"
    assert alerta.nivel == "atencao"
    assert "R$ 200,00" in alerta.sugestao


def test_reserva_completa_nao_alerta():
    meta = _meta(aportado=20000, aportado_no_mes=20000)
    assert regras.alertas_de_reserva(200000, [meta]) == []


def test_reserva_parcial_pede_so_o_que_falta():
    meta = _meta(aportado=5000, aportado_no_mes=5000)
    [alerta] = regras.alertas_de_reserva(200000, [meta])
    assert "R$ 150,00" in alerta.sugestao


def test_reserva_ignora_diferenca_abaixo_da_tolerancia():
    meta = _meta(aportado=19950, aportado_no_mes=19950)  # faltam R$ 0,50
    assert regras.alertas_de_reserva(200000, [meta]) == []


def test_reserva_ignora_meta_sem_percentual_e_mes_sem_entradas():
    assert regras.alertas_de_reserva(200000, [_meta(percentual=0)]) == []
    assert regras.alertas_de_reserva(0, [_meta()]) == []


def test_reserva_nunca_pede_mais_do_que_falta_para_a_meta():
    # faltam só R$ 20,00 para fechar a meta, embora 10% da entrada seja R$ 2.000,00
    meta = _meta(valor_alvo=10000, aportado=8000, aportado_no_mes=0)
    [alerta] = regras.alertas_de_reserva(2000000, [meta])
    assert "R$ 20,00" in alerta.sugestao


def test_reserva_ignora_meta_ja_concluida():
    meta = _meta(valor_alvo=10000, aportado=10000, aportado_no_mes=0)
    assert regras.alertas_de_reserva(200000, [meta]) == []


def test_reserva_ignora_meta_concluida_neste_mesmo_mes():
    meta = _meta(valor_alvo=10000, aportado=10000, aportado_no_mes=10000)
    assert regras.alertas_de_reserva(200000, [meta]) == []


# ---------- ordenação e descrição ----------
def test_ordenar_coloca_criticos_primeiro_sem_embaralhar_o_resto():
    a = Alerta("a", "info", "a", "", "")
    b = Alerta("b", "critico", "b", "", "")
    c = Alerta("c", "atencao", "c", "", "")
    d = Alerta("d", "atencao", "d", "", "")
    assert [x.codigo for x in regras.ordenar([a, c, b, d])] == ["b", "c", "d", "a"]


def test_descricao_das_regras_usa_os_limites_atuais():
    texto = " ".join(regras.descricao_das_regras())
    assert f"{regras.ACIMA_DA_MEDIA_ATENCAO}%" in texto
    assert f"{regras.ACIMA_DA_MEDIA_CRITICO}%" in texto


def test_alerta_e_imutavel():
    alerta = Alerta("x", "info", "t", "m", "s")
    with pytest.raises(FrozenInstanceError):
        alerta.nivel = "critico"