"""Regras do assistente financeiro.

Cada regra é uma função pura: recebe números (em centavos) e devolve um Alerta
(ou uma lista deles). Nenhuma regra acessa o banco; quem busca os dados é
src/assistant/alertas.py. Assim as regras são fáceis de testar e de entender.
"""

from dataclasses import dataclass

from src.services.metas import calcular_reserva
from src.utils.dinheiro import formatar_brl

# ---------- Limites das regras (mude aqui para deixar o assistente mais ou menos sensível) ----------
DIAS_MINIMOS = 5  # antes do 5º dia do mês ainda não dá para comparar ritmo de gastos
ACIMA_DA_MEDIA_ATENCAO = 20  # % acima da média dos meses anteriores -> atenção
ACIMA_DA_MEDIA_CRITICO = 50  # % acima da média dos meses anteriores -> crítico
TOLERANCIA_RESERVA = 100  # centavos: diferenças menores que R$ 1,00 não geram alerta

ORDEM_NIVEL = {"critico": 0, "atencao": 1, "info": 2}


@dataclass(frozen=True)
class Alerta:
    codigo: str  # identifica a regra (e, quando existe, a categoria/meta)
    nivel: str  # "critico", "atencao" ou "info"
    titulo: str
    mensagem: str  # o que está acontecendo
    sugestao: str  # o que fazer a respeito


def alertas_de_orcamento(itens: list[dict], dias_restantes: int) -> list[Alerta]:
    """Um alerta para cada categoria com orçamento em atenção (>= 80%) ou estourado (> 100%)."""
    alertas = []
    for item in itens:
        if item["situacao"] == "ok":
            continue

        categoria = item["categoria"]
        pct = item["percentual"]
        gasto = formatar_brl(item["gasto"])
        limite = formatar_brl(item["limite"])

        if item["situacao"] == "estourado":
            excesso = formatar_brl(item["gasto"] - item["limite"])
            alertas.append(
                Alerta(
                    codigo=f"orcamento_estourado_{item['categoria_id']}",
                    nivel="critico",
                    titulo=f"{categoria}: limite estourado",
                    mensagem=f"Você gastou {gasto} de um limite de {limite} ({pct:.0f}%), "
                    f"{excesso} acima do planejado.",
                    sugestao="Evite novos gastos nesta categoria até o fim do mês. Se o limite "
                    "estava irreal, ajuste-o no próximo mês em vez de ignorar o estouro.",
                )
            )
        else:
            restante = item["limite"] - item["gasto"]
            if dias_restantes > 0:
                por_dia = formatar_brl(restante // dias_restantes)
                sugestao = (
                    f"Restam {formatar_brl(restante)} para {dias_restantes} dia(s): "
                    f"cerca de {por_dia} por dia."
                )
            else:
                sugestao = f"Hoje é o último dia do mês e ainda restam {formatar_brl(restante)}."
            alertas.append(
                Alerta(
                    codigo=f"orcamento_atencao_{item['categoria_id']}",
                    nivel="atencao",
                    titulo=f"{categoria}: {pct:.0f}% do limite usado",
                    mensagem=f"Você já gastou {gasto} de um limite de {limite}.",
                    sugestao=sugestao,
                )
            )
    return alertas


def alerta_sem_orcamento(tem_limites: bool, gasto_mes: int) -> Alerta | None:
    """Há gastos no mês, mas nenhum limite foi definido: sugere criar um orçamento."""
    if tem_limites or gasto_mes <= 0:
        return None
    return Alerta(
        codigo="sem_orcamento",
        nivel="info",
        titulo="Nenhum orçamento definido para este mês",
        mensagem=f"Você já gastou {formatar_brl(gasto_mes)} este mês, mas não há limites por categoria.",
        sugestao="Defina limites na página Orçamento e metas. Dá para copiar os do mês anterior.",
    )


def alerta_gasto_acima_da_media(
    gasto_mes: int, saidas_meses_anteriores: list[int], dia: int, dias_no_mes: int
) -> Alerta | None:
    """Compara o gasto até hoje com a média dos meses anteriores, proporcional aos dias que passaram."""
    historico = [valor for valor in saidas_meses_anteriores if valor > 0]
    if not historico or dia < DIAS_MINIMOS or dias_no_mes <= 0:
        return None

    media = sum(historico) / len(historico)
    esperado = media * dia / dias_no_mes
    if esperado <= 0:
        return None

    acima = (gasto_mes - esperado) / esperado * 100
    if acima < ACIMA_DA_MEDIA_ATENCAO:
        return None

    nivel = "critico" if acima >= ACIMA_DA_MEDIA_CRITICO else "atencao"
    return Alerta(
        codigo="gasto_acima_da_media",
        nivel=nivel,
        titulo="Gastos acima do seu padrão",
        mensagem=f"Até o dia {dia} você gastou {formatar_brl(gasto_mes)}. Pela média dos meses "
        f"anteriores ({formatar_brl(round(media))} por mês), o esperado era cerca de "
        f"{formatar_brl(round(esperado))}: {acima:.0f}% a mais.",
        sugestao="Confira a lista de lançamentos do mês e veja se algum gasto fora do comum "
        "explica a diferença (por exemplo uma compra grande ou uma conta anual).",
    )


def alerta_ritmo_de_gastos(
    saldo_livre: int, gasto_mes: int, dia: int, dias_no_mes: int
) -> Alerta | None:
    """Saldo livre = saldo atual menos o que está reservado nas metas.

    Avisa quando o saldo livre acabou ou quando, no ritmo atual de gastos,
    ele não dura até o fim do mês.
    """
    if saldo_livre < 0 or (saldo_livre == 0 and gasto_mes > 0):
        return Alerta(
            codigo="saldo_esgotado",
            nivel="critico",
            titulo="Saldo livre esgotado",
            mensagem=f"Seu saldo livre está em {formatar_brl(saldo_livre)} "
            "(saldo atual menos o que está reservado nas metas).",
            sugestao="Evite gastos não essenciais. Se precisar, reveja o que está reservado nas "
            "metas, lembrando que reservar é só um controle do app.",
        )

    dias_restantes = dias_no_mes - dia
    if dia < DIAS_MINIMOS or dias_restantes <= 0 or gasto_mes <= 0:
        return None

    ritmo_diario = gasto_mes / dia
    dias_que_dura = saldo_livre / ritmo_diario
    if dias_que_dura >= dias_restantes:
        return None

    pode_gastar_por_dia = formatar_brl(saldo_livre // dias_restantes)
    return Alerta(
        codigo="ritmo_de_gastos",
        nivel="atencao",
        titulo="O saldo livre pode não durar até o fim do mês",
        mensagem=f"No ritmo atual ({formatar_brl(round(ritmo_diario))} por dia), seu saldo livre de "
        f"{formatar_brl(saldo_livre)} dura cerca de {int(dias_que_dura)} dia(s), mas faltam "
        f"{dias_restantes} para o fim do mês.",
        sugestao=f"Para chegar ao fim do mês, gaste no máximo {pode_gastar_por_dia} por dia.",
    )


def alertas_de_reserva(entradas_mes: int, metas: list[dict]) -> list[Alerta]:
    """Avisa quando o que foi reservado no mês é menor que o % combinado de cada meta.

    Cada meta precisa trazer: id, nome, valor_alvo, aportado (total), aportado_no_mes
    e percentual_entrada.
    """
    alertas = []
    for meta in metas:
        percentual = float(meta["percentual_entrada"] or 0)
        if percentual <= 0 or entradas_mes <= 0:
            continue

        # O que faltava para a meta antes das contribuições deste mês
        restante_antes = meta["valor_alvo"] - (meta["aportado"] - meta["aportado_no_mes"])
        esperado = calcular_reserva(entradas_mes, percentual, restante_antes)
        falta = esperado - meta["aportado_no_mes"]
        if falta <= TOLERANCIA_RESERVA:
            continue

        alertas.append(
            Alerta(
                codigo=f"reserva_pendente_{meta['id']}",
                nivel="atencao",
                titulo=f"{meta['nome']}: reserva do mês incompleta",
                mensagem=f"Você recebeu {formatar_brl(entradas_mes)} este mês. Com {percentual:g}% "
                f"para esta meta, o ideal era reservar {formatar_brl(esperado)}, e foram "
                f"reservados {formatar_brl(meta['aportado_no_mes'])}.",
                sugestao=f"Registre uma contribuição de {formatar_brl(falta)} na meta, em "
                "Orçamento e metas.",
            )
        )
    return alertas


def ordenar(alertas: list[Alerta]) -> list[Alerta]:
    """Críticos primeiro, depois atenção, depois informativos (mantém a ordem dentro de cada nível)."""
    return sorted(alertas, key=lambda alerta: ORDEM_NIVEL[alerta.nivel])


def descricao_das_regras() -> list[str]:
    """Texto mostrado na página do assistente, sempre em sincronia com os limites acima."""
    return [
        "**Orçamento por categoria:** avisa quando você usa 80% do limite (atenção) e quando "
        "passa de 100% (crítico).",
        f"**Gasto acima do padrão:** compara o que você gastou até hoje com a média dos meses "
        f"anteriores, proporcional aos dias do mês. Atenção a partir de {ACIMA_DA_MEDIA_ATENCAO}% "
        f"acima, crítico a partir de {ACIMA_DA_MEDIA_CRITICO}%. Só roda a partir do dia {DIAS_MINIMOS}.",
        "**Ritmo de gastos:** se o saldo livre (saldo menos o reservado nas metas) não durar até o "
        "fim do mês no ritmo atual, avisa e diz quanto dá para gastar por dia.",
        "**Saldo livre esgotado:** crítico quando o saldo livre zera ou fica negativo.",
        "**Reserva do mês:** compara o que você reservou nas metas com o percentual combinado de "
        "cada entrada recebida.",
        "**Sem orçamento:** lembra de definir limites quando há gastos e nenhum limite.",
    ]