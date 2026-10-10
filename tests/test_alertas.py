from datetime import date

import pytest

from src.assistant.alertas import gerar_alertas
from src.database import repositories as repo

pytestmark = pytest.mark.usefixtures("banco_limpo")

HOJE = date(2026, 10, 20)  # dia 20 de 31


def _base(saldo_inicial=100_000_000):
    return {
        "conta": repo.criar_conta("Carteira", "carteira", saldo_inicial),
        "renda": repo.criar_categoria("Chronomax", "entrada"),
        "lazer": repo.criar_categoria("Lazer", "saida"),
    }


def _saida(base, dia, valor):
    repo.inserir_transacao(dia, valor, "saida", base["lazer"], base["conta"])


def _codigos():
    return [alerta.codigo for alerta in gerar_alertas(HOJE)]


def test_sem_nenhum_dado_nao_ha_alertas():
    _base()
    assert gerar_alertas(HOJE) == []


def test_orcamento_estourado_gera_alerta_critico():
    base = _base()
    _saida(base, date(2026, 10, 5), 12000)
    repo.definir_orcamento(base["lazer"], "2026-10", 10000)

    [alerta] = gerar_alertas(HOJE)
    assert alerta.codigo == f"orcamento_estourado_{base['lazer']}"
    assert alerta.nivel == "critico"


def test_gastos_sem_orcamento_geram_aviso_informativo():
    base = _base()
    _saida(base, date(2026, 10, 5), 5000)
    assert _codigos() == ["sem_orcamento"]


def test_gasto_acima_da_media_dos_meses_anteriores():
    base = _base()
    for mes in (7, 8, 9):
        _saida(base, date(2026, mes, 10), 100000)
    _saida(base, date(2026, 10, 5), 80000)  # esperado até o dia 20: ~64.516 -> +24%
    assert "gasto_acima_da_media" in _codigos()


def test_media_considera_so_os_tres_meses_anteriores():
    base = _base()
    _saida(base, date(2026, 6, 10), 10_000_000)  # fora da janela, não pode puxar a média para cima
    for mes in (7, 8, 9):
        _saida(base, date(2026, mes, 10), 100000)
    _saida(base, date(2026, 10, 5), 80000)
    assert "gasto_acima_da_media" in _codigos()


def test_reserva_maior_que_o_saldo_zera_o_saldo_livre():
    repo.criar_conta("Carteira", "carteira", 10000)
    meta = repo.criar_meta("Viagem", 100000)
    repo.inserir_aporte(meta, date(2026, 10, 1), 15000)  # saldo livre = 10.000 - 15.000

    alertas = gerar_alertas(HOJE)
    assert alertas[0].codigo == "saldo_esgotado"
    assert alertas[0].nivel == "critico"


def test_reserva_do_mes_pendente_some_depois_da_contribuicao():
    base = _base()
    repo.inserir_transacao(date(2026, 10, 1), 200000, "entrada", base["renda"], base["conta"])
    meta = repo.criar_meta("Reserva", 1_000_000, None, 10)
    assert f"reserva_pendente_{meta}" in _codigos()

    repo.inserir_aporte(meta, date(2026, 10, 2), 20000)
    assert f"reserva_pendente_{meta}" not in _codigos()


def test_contribuicao_de_outro_mes_nao_quita_a_reserva_do_mes():
    base = _base()
    repo.inserir_transacao(date(2026, 10, 1), 200000, "entrada", base["renda"], base["conta"])
    meta = repo.criar_meta("Reserva", 1_000_000, None, 10)
    repo.inserir_aporte(meta, date(2026, 9, 30), 20000)
    assert f"reserva_pendente_{meta}" in _codigos()


def test_total_aportes_por_meta_respeita_o_periodo():
    reserva = repo.criar_meta("Reserva", 1_000_000)
    viagem = repo.criar_meta("Viagem", 500000)
    repo.criar_meta("Sem contribuição", 100000)
    repo.inserir_aporte(reserva, date(2026, 9, 30), 1000)  # fora (antes)
    repo.inserir_aporte(reserva, date(2026, 10, 1), 2000)  # dentro (início inclusivo)
    repo.inserir_aporte(reserva, date(2026, 10, 31), 3000)  # dentro
    repo.inserir_aporte(reserva, date(2026, 11, 1), 4000)  # fora (fim exclusivo)
    repo.inserir_aporte(viagem, date(2026, 10, 15), 500)

    totais = repo.total_aportes_por_meta(date(2026, 10, 1), date(2026, 11, 1))
    assert totais == {reserva: 5000, viagem: 500}