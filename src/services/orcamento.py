from src.database import repositories as repo
from src.utils.datas import intervalo_do_mes

LIMITE_ATENCAO = 80  # % do limite a partir do qual aparece o alerta amarelo


def situacao_do_percentual(percentual: float) -> str:
    """'ok' abaixo de 80%, 'atencao' de 80% a 100% e 'estourado' acima de 100%."""
    if percentual > 100:
        return "estourado"
    if percentual >= LIMITE_ATENCAO:
        return "atencao"
    return "ok"


def status_do_orcamento(mes: str) -> dict:
    """Limite x gasto de cada categoria com limite no mês ('AAAA-MM'), do maior uso para o menor."""
    inicio, fim = intervalo_do_mes(mes)
    gastos = {g["categoria_id"]: g["total"] for g in repo.gasto_por_categoria(inicio, fim, "saida")}

    itens = []
    for orcamento in repo.listar_orcamentos(mes):
        gasto = gastos.get(orcamento["categoria_id"], 0)
        percentual = gasto / orcamento["limite"] * 100
        itens.append({
            "categoria_id": orcamento["categoria_id"],
            "categoria": orcamento["categoria"],
            "limite": orcamento["limite"],
            "gasto": gasto,
            "restante": orcamento["limite"] - gasto,
            "percentual": percentual,
            "situacao": situacao_do_percentual(percentual),
        })
    itens.sort(key=lambda item: item["percentual"], reverse=True)

    com_limite = {item["categoria_id"] for item in itens}
    return {
        "itens": itens,
        "limite_total": sum(item["limite"] for item in itens),
        "gasto_orcado": sum(item["gasto"] for item in itens),
        "gasto_fora_do_orcamento": sum(
            total for categoria_id, total in gastos.items() if categoria_id not in com_limite
        ),
    }