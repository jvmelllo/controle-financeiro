from datetime import date

import pytest

from src.database import repositories as repo
from src.services import orcamento

pytestmark = pytest.mark.usefixtures("banco_limpo")


@pytest.fixture
def base(banco_limpo):
    return {
        "conta": repo.criar_conta("Carteira", "carteira"),
        "renda": repo.criar_categoria("Chronomax", "entrada"),
        "mercado": repo.criar_categoria("Mercado", "saida"),
        "lazer": repo.criar_categoria("Lazer", "saida"),
        "transporte": repo.criar_categoria("Transporte", "saida"),
    }


def _gasto(base, categoria, dia, valor):
    repo.inserir_transacao(dia, valor, "saida", base[categoria], base["conta"])


def test_definir_e_atualizar_limite(base):
    repo.definir_orcamento(base["mercado"], "2026-10", 50000)
    assert repo.listar_orcamentos("2026-10") == [
        {"categoria_id": base["mercado"], "categoria": "Mercado", "limite": 50000}
    ]
    repo.definir_orcamento(base["mercado"], "2026-10", 60000)  # substitui o anterior
    assert [o["limite"] for o in repo.listar_orcamentos("2026-10")] == [60000]


def test_limite_so_para_categoria_de_saida(base):
    with pytest.raises(ValueError):
        repo.definir_orcamento(base["renda"], "2026-10", 50000)


def test_limite_e_mes_invalidos(base):
    with pytest.raises(ValueError):
        repo.definir_orcamento(base["mercado"], "2026-10", 0)
    with pytest.raises(ValueError):
        repo.definir_orcamento(base["mercado"], "2026-10", -500)
    with pytest.raises(ValueError):
        repo.definir_orcamento(base["mercado"], "2026-13", 1000)
    with pytest.raises(ValueError):
        repo.definir_orcamento(base["mercado"], "2026-3", 1000)


def test_remover_orcamento(base):
    repo.definir_orcamento(base["mercado"], "2026-10", 50000)
    repo.remover_orcamento(base["mercado"], "2026-10")
    assert repo.listar_orcamentos("2026-10") == []


def test_copiar_orcamentos_sem_sobrescrever(base):
    repo.definir_orcamento(base["mercado"], "2026-10", 50000)
    repo.definir_orcamento(base["lazer"], "2026-10", 20000)
    repo.definir_orcamento(base["mercado"], "2026-11", 99900)  # já existe no mês de destino

    assert repo.copiar_orcamentos("2026-10", "2026-11") == 1  # só o Lazer foi copiado
    limites = {o["categoria"]: o["limite"] for o in repo.listar_orcamentos("2026-11")}
    assert limites == {"Mercado": 99900, "Lazer": 20000}


@pytest.mark.parametrize("percentual, esperado", [
    (0, "ok"), (79.9, "ok"), (80, "atencao"), (100, "atencao"), (100.1, "estourado"),
])
def test_situacao_do_percentual(percentual, esperado):
    assert orcamento.situacao_do_percentual(percentual) == esperado


def test_status_do_orcamento(base):
    repo.definir_orcamento(base["mercado"], "2026-10", 50000)
    repo.definir_orcamento(base["lazer"], "2026-10", 20000)
    _gasto(base, "mercado", date(2026, 10, 5), 45000)
    _gasto(base, "mercado", date(2026, 9, 20), 10000)   # outro mês: não conta
    _gasto(base, "lazer", date(2026, 10, 8), 25000)
    _gasto(base, "transporte", date(2026, 10, 9), 7000)  # categoria sem limite

    status = orcamento.status_do_orcamento("2026-10")

    assert [i["categoria"] for i in status["itens"]] == ["Lazer", "Mercado"]  # do maior uso ao menor
    lazer, mercado = status["itens"]
    assert (lazer["gasto"], lazer["restante"], lazer["situacao"]) == (25000, -5000, "estourado")
    assert (mercado["gasto"], mercado["restante"], mercado["situacao"]) == (45000, 5000, "atencao")
    assert status["limite_total"] == 70000
    assert status["gasto_orcado"] == 70000
    assert status["gasto_fora_do_orcamento"] == 7000


def test_status_sem_gastos(base):
    repo.definir_orcamento(base["mercado"], "2026-10", 50000)
    item = orcamento.status_do_orcamento("2026-10")["itens"][0]
    assert (item["gasto"], item["percentual"], item["situacao"]) == (0, 0, "ok")