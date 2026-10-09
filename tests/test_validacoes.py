from datetime import date

import pytest

from src.services.validacoes import validar_lancamento

HOJE = date(2026, 10, 9)


def test_lancamento_valido():
    assert validar_lancamento(date(2026, 10, 1), 1500, HOJE) == ([], [])


@pytest.mark.parametrize("centavos", [0, -100])
def test_valor_zero_ou_negativo(centavos):
    erros, _ = validar_lancamento(date(2026, 10, 1), centavos, HOJE)
    assert erros


def test_valor_alto_demais():
    erros, _ = validar_lancamento(date(2026, 10, 1), 100_000_001, HOJE)
    assert erros


def test_data_no_futuro_gera_aviso_sem_erro():
    erros, avisos = validar_lancamento(date(2026, 10, 20), 1500, HOJE)
    assert erros == [] and len(avisos) == 1


def test_data_antiga_demais():
    erros, _ = validar_lancamento(date(1999, 12, 31), 1500, HOJE)
    assert erros