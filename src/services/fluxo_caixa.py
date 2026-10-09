from src.database import repositories as repo
from src.utils.datas import intervalo_do_mes


def saldo_atual() -> int:
    """Saldo inicial das contas + todas as entradas - todas as saídas (centavos)."""
    totais = repo.somar_por_tipo()
    return repo.total_saldo_inicial() + totais["entrada"] - totais["saida"]


def resumo_do_mes(mes: str) -> dict:
    inicio, fim = intervalo_do_mes(mes)
    totais = repo.somar_por_tipo(inicio, fim)
    return {
        "mes": mes,
        "entradas": totais["entrada"],
        "saidas": totais["saida"],
        "resultado": totais["entrada"] - totais["saida"],
    }


def totais_mensais() -> list[dict]:
    return [
        {**linha, "resultado": linha["entradas"] - linha["saidas"]}
        for linha in repo.totais_por_mes()
    ]


def gastos_por_categoria(mes: str) -> list[dict]:
    inicio, fim = intervalo_do_mes(mes)
    return repo.gasto_por_categoria(inicio, fim, "saida")


def maior_gasto_do_mes(mes: str) -> dict | None:
    gastos = repo.listar_transacoes(mes=mes, tipo="saida")
    return max(gastos, key=lambda t: t["valor"]) if gastos else None


def evolucao_do_saldo() -> list[dict]:
    """Saldo ao final de cada mês, em ordem cronológica."""
    saldo = repo.total_saldo_inicial()
    evolucao = []
    for linha in totais_mensais():
        saldo += linha["resultado"]
        evolucao.append({"mes": linha["mes"], "saldo": saldo})
    return evolucao