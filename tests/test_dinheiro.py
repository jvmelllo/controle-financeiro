import pytest

from src.utils.dinheiro import centavos_para_reais, formatar_brl, reais_para_centavos


@pytest.mark.parametrize("entrada, esperado", [
    ("10,10", 1010),
    ("1.234,56", 123456),
    ("R$ 1.234,56", 123456),
    ("1234.56", 123456),
    (12.5, 1250),
    (0, 0),
    ("-50,00", -5000),
])
def test_reais_para_centavos(entrada, esperado):
    assert reais_para_centavos(entrada) == esperado


def test_valor_invalido():
    with pytest.raises(ValueError):
        reais_para_centavos("abc")


def test_centavos_para_reais():
    assert str(centavos_para_reais(1010)) == "10.1"


def test_formatar_brl():
    assert formatar_brl(123456) == "R$ 1.234,56"
    assert formatar_brl(5) == "R$ 0,05"
    assert formatar_brl(-5000) == "-R$ 50,00"