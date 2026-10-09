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

def test_categoria_duplicada():
    repo.criar_categoria("Lazer", "saida")
    with pytest.raises(ValueError):
        repo.criar_categoria("Lazer", "saida")


def test_nome_vazio():
    with pytest.raises(ValueError):
        repo.criar_categoria("   ", "saida")


def test_desativar_categoria():
    cid = repo.criar_categoria("Lazer", "saida")
    repo.definir_categoria_ativa(cid, False)
    assert repo.listar_categorias() == []
    assert len(repo.listar_categorias(apenas_ativas=False)) == 1


def test_renomear_categoria():
    cid = repo.criar_categoria("Lazer", "saida")
    repo.renomear_categoria(cid, "Diversão")
    assert repo.listar_categorias()[0]["nome"] == "Diversão"


def test_atualizar_conta():
    cid = repo.criar_conta("Carteira", "carteira")
    repo.atualizar_conta(cid, "Carteira nova", 2500)
    conta = repo.listar_contas()[0]
    assert conta["nome"] == "Carteira nova" and conta["saldo_inicial"] == 2500


def test_conta_duplicada_e_tipo_invalido():
    repo.criar_conta("Carteira", "carteira")
    with pytest.raises(ValueError):
        repo.criar_conta("Carteira", "carteira")
    with pytest.raises(ValueError):
        repo.criar_conta("Outra", "tipo_inexistente")