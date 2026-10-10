from datetime import date

import pytest

from src.database import repositories as repo
from src.services import metas as servico_metas


# ---------- repositório (usa o banco de teste) ----------
def test_criar_e_listar_meta(banco_limpo):
    mid = repo.criar_meta("Reserva de emergência", 100000, date(2027, 6, 1), 10)
    assert repo.listar_metas() == [{
        "id": mid, "nome": "Reserva de emergência", "valor_alvo": 100000,
        "prazo": date(2027, 6, 1), "percentual_entrada": 10.0, "aportado": 0,
    }]


def test_validacoes_da_meta(banco_limpo):
    with pytest.raises(ValueError):
        repo.criar_meta("   ", 100000)
    with pytest.raises(ValueError):
        repo.criar_meta("Viagem", 0)
    with pytest.raises(ValueError):
        repo.criar_meta("Viagem", 100000, percentual_entrada=101)
    with pytest.raises(ValueError):
        repo.criar_meta("Viagem", 100000, percentual_entrada=-1)


def test_aportes_somam_no_progresso(banco_limpo):
    mid = repo.criar_meta("Reserva", 100000)
    repo.inserir_aporte(mid, date(2026, 10, 1), 20000)
    repo.inserir_aporte(mid, date(2026, 10, 5), 5000)

    assert repo.listar_metas()[0]["aportado"] == 25000
    assert repo.total_reservado() == 25000
    assert [a["valor"] for a in repo.listar_aportes(mid)] == [5000, 20000]  # mais recente primeiro


def test_aporte_invalido(banco_limpo):
    mid = repo.criar_meta("Reserva", 100000)
    with pytest.raises(ValueError):
        repo.inserir_aporte(mid, date(2026, 10, 1), 0)
    with pytest.raises(ValueError):
        repo.inserir_aporte(999999, date(2026, 10, 1), 1000)  # meta inexistente


def test_excluir_aporte(banco_limpo):
    mid = repo.criar_meta("Reserva", 100000)
    aid = repo.inserir_aporte(mid, date(2026, 10, 1), 20000)
    repo.excluir_aporte(aid)
    assert repo.total_reservado() == 0


def test_excluir_meta_apaga_aportes(banco_limpo):
    mid = repo.criar_meta("Reserva", 100000)
    repo.inserir_aporte(mid, date(2026, 10, 1), 20000)
    repo.excluir_meta(mid)
    assert repo.listar_metas() == []
    assert repo.listar_aportes(mid) == []
    assert repo.total_reservado() == 0


def test_atualizar_meta(banco_limpo):
    mid = repo.criar_meta("Reserva", 100000)
    repo.atualizar_meta(mid, "Reserva maior", 200000, date(2027, 1, 1), 15)
    meta = repo.listar_metas()[0]
    assert (meta["nome"], meta["valor_alvo"], meta["prazo"], meta["percentual_entrada"]) == (
        "Reserva maior", 200000, date(2027, 1, 1), 15.0,
    )


def test_sugestoes_de_reserva(banco_limpo):
    repo.criar_meta("A reserva", 100000, percentual_entrada=10)
    repo.criar_meta("B sem percentual", 100000)
    concluida = repo.criar_meta("C concluída", 1000, percentual_entrada=50)
    repo.inserir_aporte(concluida, date(2026, 10, 1), 1000)
    quase = repo.criar_meta("D quase lá", 500, percentual_entrada=5)
    repo.inserir_aporte(quase, date(2026, 10, 1), 400)  # faltam 100

    sugestoes = servico_metas.sugestoes_de_reserva(30000)
    assert [(s["meta"], s["valor"]) for s in sugestoes] == [("A reserva", 3000), ("D quase lá", 100)]


# ---------- regras puras (não usam o banco) ----------
@pytest.mark.parametrize("entrada, percentual, restante, esperado", [
    (30000, 10, 100000, 3000),
    (30000, 10, 2000, 2000),     # não passa do que falta na meta
    (10050, 10, 100000, 1005),
    (10005, 10, 100000, 1001),   # 1000,5 arredonda para cima
    (30000, 0, 100000, 0),
    (30000, 10, 0, 0),
])
def test_calcular_reserva(entrada, percentual, restante, esperado):
    assert servico_metas.calcular_reserva(entrada, percentual, restante) == esperado


def test_progresso_da_meta_com_prazo():
    meta = {"valor_alvo": 100000, "aportado": 25000, "prazo": date(2026, 12, 10)}
    progresso = servico_metas.progresso_da_meta(meta, hoje=date(2026, 10, 10))
    assert progresso["percentual"] == 25
    assert progresso["restante"] == 75000
    assert progresso["por_mes"] == 37500  # 2 meses até o prazo
    assert not progresso["atrasada"] and not progresso["concluida"]

    meta = {"valor_alvo": 100, "aportado": 0, "prazo": date(2027, 1, 10)}
    assert servico_metas.progresso_da_meta(meta, hoje=date(2026, 10, 10))["por_mes"] == 34  # arredonda para cima


def test_progresso_da_meta_vencida_sem_prazo_e_concluida():
    hoje = date(2026, 10, 10)
    vencida = servico_metas.progresso_da_meta(
        {"valor_alvo": 100000, "aportado": 1000, "prazo": date(2026, 9, 1)}, hoje=hoje
    )
    assert vencida["atrasada"] and vencida["por_mes"] is None

    sem_prazo = servico_metas.progresso_da_meta(
        {"valor_alvo": 100000, "aportado": 1000, "prazo": None}, hoje=hoje
    )
    assert not sem_prazo["atrasada"] and sem_prazo["por_mes"] is None

    concluida = servico_metas.progresso_da_meta(
        {"valor_alvo": 100000, "aportado": 120000, "prazo": date(2026, 9, 1)}, hoje=hoje
    )
    assert concluida["concluida"] and concluida["percentual"] == 100
    assert concluida["restante"] == 0 and not concluida["atrasada"] and concluida["por_mes"] is None


def test_progresso_da_meta_com_prazo_no_mes_atual():
    meta = {"valor_alvo": 100000, "aportado": 0, "prazo": date(2026, 10, 20)}
    assert servico_metas.progresso_da_meta(meta, hoje=date(2026, 10, 10))["por_mes"] == 100000