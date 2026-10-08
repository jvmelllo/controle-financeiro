from datetime import date

import pytest

from src.database import repositories as repo

pytestmark = pytest.mark.usefixtures("banco_limpo")


@pytest.fixture
def base():
    return {
        "conta": repo.criar_conta("Carteira", "carteira"),
        "renda": repo.criar_categoria("Chronomax", "entrada"),
        "mercado": repo.criar_categoria("Mercado", "saida"),
    }


def _saida(base, dia, valor):
    return repo.inserir_transacao(dia, valor, "saida", base["mercado"], base["conta"])


def test_inserir_e_buscar(base):
    tid = repo.inserir_transacao(
        date(2026, 10, 5), 15050, "saida", base["mercado"], base["conta"], "Compras", "pix"
    )
    t = repo.buscar_transacao(tid)
    assert t["valor"] == 15050
    assert t["categoria"] == "Mercado"
    assert t["conta"] == "Carteira"
    assert t["data"] == date(2026, 10, 5)


def test_categoria_incompativel_com_tipo(base):
    with pytest.raises(ValueError):
        repo.inserir_transacao(date(2026, 10, 5), 1000, "entrada", base["mercado"], base["conta"])


@pytest.mark.parametrize("valor", [0, -100, 10.5, "10"])
def test_valor_invalido(base, valor):
    with pytest.raises(ValueError):
        _saida(base, date(2026, 10, 5), valor)


def test_listar_por_mes_e_tipo(base):
    _saida(base, date(2026, 9, 30), 1000)
    _saida(base, date(2026, 10, 1), 2000)
    repo.inserir_transacao(date(2026, 10, 31), 50000, "entrada", base["renda"], base["conta"])
    _saida(base, date(2026, 11, 1), 3000)

    assert [t["valor"] for t in repo.listar_transacoes(mes="2026-10")] == [50000, 2000]
    assert [t["valor"] for t in repo.listar_transacoes(mes="2026-10", tipo="saida")] == [2000]


def test_atualizar(base):
    tid = _saida(base, date(2026, 10, 5), 1000)
    assert repo.atualizar_transacao(tid, valor=2500, descricao="Corrigido") is True
    t = repo.buscar_transacao(tid)
    assert t["valor"] == 2500 and t["descricao"] == "Corrigido"
    assert repo.atualizar_transacao(999999, valor=100) is False


def test_atualizar_campo_nao_permitido(base):
    tid = _saida(base, date(2026, 10, 5), 1000)
    with pytest.raises(ValueError):
        repo.atualizar_transacao(tid, id=99)


def test_excluir(base):
    tid = _saida(base, date(2026, 10, 5), 1000)
    assert repo.excluir_transacao(tid) is True
    assert repo.buscar_transacao(tid) is None
    assert repo.excluir_transacao(tid) is False