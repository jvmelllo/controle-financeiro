"""Junta os dados do banco com as regras de src/assistant/regras.py."""

from datetime import date

from src.assistant import regras
from src.assistant.regras import Alerta
from src.database import repositories as repo
from src.services import fluxo_caixa, orcamento
from src.utils.datas import deslocar_meses, intervalo_do_mes

MESES_DE_HISTORICO = 3  # quantos meses anteriores entram na média de gastos


def gerar_alertas(hoje: date | None = None) -> list[Alerta]:
    """Analisa o mês de `hoje` e devolve os alertas, dos mais urgentes aos menos."""
    hoje = hoje or date.today()
    mes = f"{hoje.year:04d}-{hoje.month:02d}"
    inicio, fim = intervalo_do_mes(mes)
    dias_no_mes = (fim - inicio).days
    dias_restantes = dias_no_mes - hoje.day

    resumo = fluxo_caixa.resumo_do_periodo(inicio, fim)
    gasto_mes = resumo["saidas"]
    entradas_mes = resumo["entradas"]

    # Saldo livre = saldo atual - o que está reservado nas metas
    saldo_livre = fluxo_caixa.saldo_atual() - repo.total_reservado()

    # Média de saídas dos meses anteriores (só meses que tiveram movimento)
    inicio_historico = deslocar_meses(inicio, -MESES_DE_HISTORICO)
    saidas_anteriores = [m["saidas"] for m in fluxo_caixa.totais_mensais(inicio_historico, inicio)]

    # Metas com o quanto foi contribuído neste mês
    contribuicoes_do_mes = repo.total_aportes_por_meta(inicio, fim)
    metas = [
        {**meta, "aportado_no_mes": contribuicoes_do_mes.get(meta["id"], 0)}
        for meta in repo.listar_metas()
    ]

    status = orcamento.status_do_orcamento(mes)

    alertas: list[Alerta] = []
    alertas += regras.alertas_de_orcamento(status["itens"], dias_restantes)
    alertas.append(regras.alerta_sem_orcamento(bool(status["itens"]), gasto_mes))
    alertas.append(
        regras.alerta_gasto_acima_da_media(gasto_mes, saidas_anteriores, hoje.day, dias_no_mes)
    )
    alertas.append(regras.alerta_ritmo_de_gastos(saldo_livre, gasto_mes, hoje.day, dias_no_mes))
    alertas += regras.alertas_de_reserva(entradas_mes, metas)

    return regras.ordenar([alerta for alerta in alertas if alerta is not None])