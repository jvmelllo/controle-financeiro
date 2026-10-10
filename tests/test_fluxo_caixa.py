from datetime import date

import pytest

from src.database import repositories as repo
from src.services import fluxo_caixa


@pytest.fixture
def cenario(banco_limpo):
    conta = repo.criar_conta("Carteira", "carteira", saldo_inicial=10000)
    renda = repo.criar_categoria("Chronomax", "entrada")
    mercado = repo.criar_categoria("Mercado", "saida")
    lazer = repo.criar_categoria("Lazer", "saida")
    repo.inserir_transacao(date(2026, 9, 10), 20000, "entrada", renda, conta)
    repo.inserir_transacao(date(2026, 9, 12), 5000, "saida", mercado, conta)
    repo.inserir_transacao(date(2026, 10, 3), 30000, "entrada", renda, conta)
    repo.inserir_transacao(date(2026, 10, 4), 8000, "saida", mercado, conta)
    repo.inserir_transacao(date(2026, 10, 20), 12000, "saida", lazer, conta)


def test_saldo_atual(cenario):
    assert fluxo_caixa.saldo_atual() == 35000  # 10000 + 50000 - 25000


def test_resumo_do_mes(cenario):
    assert fluxo_caixa.resumo_do_mes("2026-10") == {
        "mes": "2026-10", "entradas": 30000, "saidas": 20000, "resultado": 10000,
    }


def test_resumo_de_mes_sem_movimento(cenario):
    assert fluxo_caixa.resumo_do_mes("2026-01") == {
        "mes": "2026-01", "entradas": 0, "saidas": 0, "resultado": 0,
    }


def test_totais_mensais(cenario):
    assert fluxo_caixa.totais_mensais() == [
        {"mes": "2026-09", "entradas": 20000, "saidas": 5000, "resultado": 15000},
        {"mes": "2026-10", "entradas": 30000, "saidas": 20000, "resultado": 10000},
    ]


def test_gastos_por_categoria(cenario):
    gastos = fluxo_caixa.gastos_por_categoria("2026-10")
    assert [(g["categoria"], g["total"]) for g in gastos] == [("Lazer", 12000), ("Mercado", 8000)]


def test_maior_gasto_do_mes(cenario):
    maior = fluxo_caixa.maior_gasto_do_mes("2026-10")
    assert maior["valor"] == 12000 and maior["categoria"] == "Lazer"
    assert fluxo_caixa.maior_gasto_do_mes("2025-01") is None


def test_evolucao_do_saldo(cenario):
    assert fluxo_caixa.evolucao_do_saldo() == [
        {"mes": "2026-09", "saldo": 25000},
        {"mes": "2026-10", "saldo": 35000},
    ]

def test_resumo_do_periodo(cenario):
    assert fluxo_caixa.resumo_do_periodo(date(2026, 10, 1), date(2026, 11, 1)) == {
        "entradas": 30000, "saidas": 20000, "resultado": 10000,
    }


def test_totais_mensais_no_periodo(cenario):
    totais = fluxo_caixa.totais_mensais(date(2026, 10, 1), date(2026, 11, 1))
    assert [t["mes"] for t in totais] == ["2026-10"]


def test_evolucao_do_saldo_no_periodo(cenario):
    # o saldo de outubro considera o que veio antes: 10000 + 20000 - 5000 + 10000
    assert fluxo_caixa.evolucao_do_saldo(date(2026, 10, 1), date(2026, 11, 1)) == [
        {"mes": "2026-10", "saldo": 35000},
    ]


def test_gastos_por_categoria_no_periodo(cenario):
    gastos = fluxo_caixa.gastos_por_categoria_no_periodo(date(2026, 9, 1), date(2026, 11, 1))
    assert [(g["categoria"], g["total"]) for g in gastos] == [("Mercado", 13000), ("Lazer", 12000)]


def test_variacao_percentual():
    assert fluxo_caixa.variacao_percentual(15000, 10000) == 50.0
    assert fluxo_caixa.variacao_percentual(10000, 20000) == -50.0
    assert fluxo_caixa.variacao_percentual(5000, 0) is None    

def test_evolucao_diaria_do_saldo(cenario):
    evolucao = fluxo_caixa.evolucao_diaria_do_saldo(
        date(2026, 10, 1), date(2026, 11, 1), hoje=date(2026, 10, 25)
    )
    saldo_por_dia = {e["data"]: e["saldo"] for e in evolucao}
    assert len(evolucao) == 25                       # 1º a 25 de outubro
    assert evolucao[0]["saldo"] == 25000             # saldo herdado de setembro
    assert saldo_por_dia[date(2026, 10, 3)] == 55000
    assert saldo_por_dia[date(2026, 10, 4)] == 47000
    assert saldo_por_dia[date(2026, 10, 19)] == 47000  # dia sem movimento repete o saldo
    assert saldo_por_dia[date(2026, 10, 20)] == 35000
    assert evolucao[-1] == {"data": date(2026, 10, 25), "saldo": 35000}


def test_evolucao_diaria_vai_ate_lancamento_futuro(cenario):
    evolucao = fluxo_caixa.evolucao_diaria_do_saldo(
        date(2026, 10, 1), date(2026, 11, 1), hoje=date(2026, 10, 5)
    )
    assert evolucao[-1]["data"] == date(2026, 10, 20)


def test_evolucao_diaria_de_periodo_futuro(cenario):
    assert fluxo_caixa.evolucao_diaria_do_saldo(
        date(2026, 12, 1), date(2027, 1, 1), hoje=date(2026, 10, 25)
    ) == []    