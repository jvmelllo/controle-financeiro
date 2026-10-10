from datetime import date

from src.utils.datas import (
    deslocar_meses,
    intervalo_do_ano,
    intervalo_do_trimestre,
    periodo_anterior,
    rotulo_mes,
)


def test_rotulo_mes():
    assert rotulo_mes("2026-10") == "out/2026"
    assert rotulo_mes("2026-01") == "jan/2026"


def test_deslocar_meses():
    assert deslocar_meses(date(2026, 1, 15), -1) == date(2025, 12, 1)
    assert deslocar_meses(date(2026, 11, 5), 3) == date(2027, 2, 1)
    assert deslocar_meses(date(2026, 10, 9), 0) == date(2026, 10, 1)


def test_intervalo_do_trimestre():
    assert intervalo_do_trimestre(2026, 1) == (date(2026, 1, 1), date(2026, 4, 1))
    assert intervalo_do_trimestre(2026, 4) == (date(2026, 10, 1), date(2027, 1, 1))


def test_intervalo_do_ano():
    assert intervalo_do_ano(2026) == (date(2026, 1, 1), date(2027, 1, 1))


def test_periodo_anterior_de_mes_e_trimestre():
    assert periodo_anterior(date(2026, 3, 1), date(2026, 4, 1), 1) == (date(2026, 2, 1), date(2026, 3, 1))
    assert periodo_anterior(date(2026, 1, 1), date(2026, 4, 1), 3) == (date(2025, 10, 1), date(2026, 1, 1))


def test_periodo_anterior_personalizado():
    assert periodo_anterior(date(2026, 10, 10), date(2026, 10, 20)) == (date(2026, 9, 30), date(2026, 10, 10))