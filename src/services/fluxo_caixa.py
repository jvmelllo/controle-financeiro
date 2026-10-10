from src.database import repositories as repo
from src.utils.datas import intervalo_do_mes
from datetime import date, timedelta

from src.database import repositories as repo
from src.utils.datas import intervalo_do_mes


def saldo_atual() -> int:
    """Saldo inicial das contas + todas as entradas - todas as saídas (centavos)."""
    totais = repo.somar_por_tipo()
    return repo.total_saldo_inicial() + totais["entrada"] - totais["saida"]


def resumo_do_periodo(inicio, fim) -> dict:
    """Totais com inicio <= data < fim (centavos)."""
    totais = repo.somar_por_tipo(inicio, fim)
    return {
        "entradas": totais["entrada"],
        "saidas": totais["saida"],
        "resultado": totais["entrada"] - totais["saida"],
    }


def resumo_do_mes(mes: str) -> dict:
    inicio, fim = intervalo_do_mes(mes)
    return {"mes": mes, **resumo_do_periodo(inicio, fim)}


def variacao_percentual(atual: int, anterior: int) -> float | None:
    """Variação em % em relação ao período anterior; None se não há base de comparação."""
    if anterior == 0:
        return None
    return (atual - anterior) / abs(anterior) * 100


def totais_mensais(inicio=None, fim=None) -> list[dict]:
    return [
        {**linha, "resultado": linha["entradas"] - linha["saidas"]}
        for linha in repo.totais_por_mes(inicio, fim)
    ]


def gastos_por_categoria(mes: str) -> list[dict]:
    inicio, fim = intervalo_do_mes(mes)
    return repo.gasto_por_categoria(inicio, fim, "saida")


def gastos_por_categoria_no_periodo(inicio, fim) -> list[dict]:
    return repo.gasto_por_categoria(inicio, fim, "saida")


def maior_gasto_do_mes(mes: str) -> dict | None:
    gastos = repo.listar_transacoes(mes=mes, tipo="saida")
    return max(gastos, key=lambda t: t["valor"]) if gastos else None


def evolucao_do_saldo(inicio=None, fim=None) -> list[dict]:
    """Saldo ao final de cada mês do período, em ordem cronológica."""
    saldo = repo.total_saldo_inicial()
    if inicio:
        antes = repo.somar_por_tipo(fim=inicio)  # tudo o que aconteceu antes do período
        saldo += antes["entrada"] - antes["saida"]
    evolucao = []
    for linha in totais_mensais(inicio, fim):
        saldo += linha["resultado"]
        evolucao.append({"mes": linha["mes"], "saldo": saldo})
    return evolucao

def evolucao_diaria_do_saldo(inicio, fim, hoje: date | None = None) -> list[dict]:
    """Saldo ao final de cada dia do período; dias sem movimento repetem o saldo anterior.

    A série vai até hoje (ou até o último lançamento do período, se houver
    lançamentos futuros), sem estender a linha por dias que ainda não chegaram.
    """
    hoje = hoje or date.today()
    saldo = repo.total_saldo_inicial()
    antes = repo.somar_por_tipo(fim=inicio)  # tudo o que aconteceu antes do período
    saldo += antes["entrada"] - antes["saida"]

    variacao_por_dia = {
        linha["data"]: linha["entradas"] - linha["saidas"]
        for linha in repo.totais_por_dia(inicio, fim)
    }
    dia_final = min(fim - timedelta(days=1), max([hoje, *variacao_por_dia]))

    evolucao = []
    dia = inicio
    while dia <= dia_final:
        saldo += variacao_por_dia.get(dia, 0)
        evolucao.append({"data": dia, "saldo": saldo})
        dia += timedelta(days=1)
    return evolucao