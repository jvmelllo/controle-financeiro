from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.database import repositories as repo


def progresso_da_meta(meta: dict, hoje: date | None = None) -> dict:
    """Andamento de uma meta ({'valor_alvo', 'aportado', 'prazo'}, valores em centavos)."""
    hoje = hoje or date.today()
    restante = max(meta["valor_alvo"] - meta["aportado"], 0)
    concluida = restante == 0
    prazo = meta["prazo"]

    por_mes = None
    if prazo and prazo >= hoje and not concluida:
        meses = max((prazo.year - hoje.year) * 12 + (prazo.month - hoje.month), 1)
        por_mes = -(-restante // meses)  # divisão arredondada para cima

    return {
        "percentual": min(meta["aportado"] / meta["valor_alvo"] * 100, 100),
        "restante": restante,
        "concluida": concluida,
        "atrasada": bool(prazo) and prazo < hoje and not concluida,
        "por_mes": por_mes,
    }


def calcular_reserva(valor_entrada: int, percentual: float, restante: int) -> int:
    """Quanto separar de uma entrada (centavos): o percentual, sem passar do que falta na meta."""
    if percentual <= 0 or restante <= 0:
        return 0
    valor = (Decimal(valor_entrada) * Decimal(str(percentual)) / 100).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return min(int(valor), restante)


def sugestoes_de_reserva(valor_entrada: int) -> list[dict]:
    """Sugestão de aporte, por meta com percentual definido e ainda não concluída."""
    sugestoes = []
    for meta in repo.listar_metas():
        restante = meta["valor_alvo"] - meta["aportado"]
        valor = calcular_reserva(valor_entrada, meta["percentual_entrada"], restante)
        if valor > 0:
            sugestoes.append({
                "meta_id": meta["id"],
                "meta": meta["nome"],
                "percentual": meta["percentual_entrada"],
                "valor": valor,
            })
    return sugestoes