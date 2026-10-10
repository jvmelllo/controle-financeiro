from datetime import date

import pytest

from src.assistant.contexto import montar_contexto
from src.database import repositories as repo

pytestmark = pytest.mark.usefixtures("banco_limpo")

HOJE = date(2026, 10, 20)


def _dados():
    conta = repo.criar_conta("ContaSecretaXYZ", "carteira", 500000)
    renda = repo.criar_categoria("Chronomax", "entrada")
    lazer = repo.criar_categoria("Lazer", "saida")
    repo.inserir_transacao(date(2026, 10, 1), 200000, "entrada", renda, conta)
    repo.inserir_transacao(
        date(2026, 10, 5), 12000, "saida", lazer, conta, "DescricaoPrivadaXYZ", "pix"
    )
    repo.definir_orcamento(lazer, "2026-10", 10000)
    repo.criar_meta("Reserva da emergência", 340000, None, 10)
    return conta


def test_contexto_traz_os_totais_agregados():
    _dados()
    contexto = montar_contexto(HOJE)
    assert "Data de referência: 20/10/2026" in contexto
    assert "Saldo atual: R$ 6.880,00" in contexto  # 5.000 + 2.000 - 120
    assert "- Entradas: R$ 2.000,00" in contexto
    assert "- Lazer: R$ 120,00" in contexto
    assert "Lazer: gasto R$ 120,00 de R$ 100,00 (120%)" in contexto
    assert "Reserva da emergência" in contexto


def test_contexto_traz_os_destaques_ja_calculados():
    _dados()
    contexto = montar_contexto(HOJE)
    assert "Média de saídas por dia no mês: R$ 6,00" in contexto  # R$ 120 em 20 dias
    assert "Saídas previstas até o fim do mês, no ritmo atual: R$ 186,00" in contexto  # R$ 6 x 31 dias
    assert "Maior categoria de gasto: Lazer (100% das saídas do mês)" in contexto


def test_contexto_nao_vaza_descricoes_nem_nomes_de_contas():
    _dados()
    contexto = montar_contexto(HOJE)
    assert "DescricaoPrivadaXYZ" not in contexto
    assert "ContaSecretaXYZ" not in contexto


def test_contexto_inclui_os_alertas_ativos():
    _dados()
    assert "[critico] Lazer: limite estourado" in montar_contexto(HOJE)


def test_contexto_com_banco_vazio_nao_quebra():
    contexto = montar_contexto(HOJE)
    assert "Sem gastos no mês." in contexto
    assert "Nenhum limite definido." in contexto
    assert "Nenhuma meta criada." in contexto
    assert "Nenhum alerta." in contexto