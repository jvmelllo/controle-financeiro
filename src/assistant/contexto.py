"""Monta o resumo dos números que a IA recebe.

Só entram dados AGREGADOS (totais, categorias, orçamentos, metas e alertas).
Descrições de lançamentos, nomes de contas e datas de cada compra nunca saem daqui.
"""

from datetime import date

from src.assistant.alertas import gerar_alertas
from src.database import repositories as repo
from src.services import fluxo_caixa, orcamento
from src.services import metas as servico_metas
from src.utils.datas import deslocar_meses, intervalo_do_mes
from src.utils.dinheiro import formatar_brl

MESES_NO_RESUMO = 3  # meses anteriores incluídos no resumo


def _secao(titulo: str, linhas: list[str], vazio: str) -> list[str]:
    return ["", titulo, *(linhas or [vazio])]


def montar_contexto(hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    mes = f"{hoje.year:04d}-{hoje.month:02d}"
    inicio, fim = intervalo_do_mes(mes)
    dias_no_mes = (fim - inicio).days

    saldo = fluxo_caixa.saldo_atual()
    reservado = repo.total_reservado()
    resumo = fluxo_caixa.resumo_do_periodo(inicio, fim)

    texto = [f"Data de referência: {hoje:%d/%m/%Y} (dia {hoje.day} de {dias_no_mes} do mês)."]

    texto += _secao(
        "SALDO",
        [
            f"- Saldo atual: {formatar_brl(saldo)}",
            f"- Reservado nas metas: {formatar_brl(reservado)}",
            f"- Livre para gastar: {formatar_brl(saldo - reservado)}",
        ],
        "",
    )

    texto += _secao(
        "MÊS ATUAL",
        [
            f"- Entradas: {formatar_brl(resumo['entradas'])}",
            f"- Saídas: {formatar_brl(resumo['saidas'])}",
            f"- Resultado: {formatar_brl(resumo['resultado'])}",
        ],
        "",
    )

    gastos = sorted(fluxo_caixa.gastos_por_categoria(mes), key=lambda g: g["total"], reverse=True)

    # Contas já feitas aqui: modelos pequenos erram aritmética, então recebem os números prontos.
    destaques = []
    if resumo["saidas"] > 0:
        media_dia = round(resumo["saidas"] / hoje.day)
        destaques.append(f"- Média de saídas por dia no mês: {formatar_brl(media_dia)}")
        destaques.append(
            f"- Saídas previstas até o fim do mês, no ritmo atual: {formatar_brl(media_dia * dias_no_mes)}"
        )
    if gastos and resumo["saidas"] > 0:
        maior = gastos[0]
        destaques.append(
            f"- Maior categoria de gasto: {maior['categoria']} "
            f"({maior['total'] / resumo['saidas'] * 100:.0f}% das saídas do mês)"
        )
    texto += _secao("DESTAQUES DO MÊS", destaques, "- Sem gastos no mês.")

    anteriores = fluxo_caixa.totais_mensais(deslocar_meses(inicio, -MESES_NO_RESUMO), inicio)
    texto += _secao(
        "MESES ANTERIORES",
        [
            f"- {m['mes']}: entradas {formatar_brl(m['entradas'])}, saídas {formatar_brl(m['saidas'])}"
            for m in anteriores
        ],
        "- Sem histórico.",
    )

    texto += _secao(
        "GASTOS POR CATEGORIA NO MÊS",
        [f"- {g['categoria']}: {formatar_brl(g['total'])}" for g in gastos],
        "- Nenhum gasto registrado.",
    )

    itens = orcamento.status_do_orcamento(mes)["itens"]
    texto += _secao(
        "ORÇAMENTO DO MÊS (limite por categoria)",
        [
            f"- {i['categoria']}: gasto {formatar_brl(i['gasto'])} de {formatar_brl(i['limite'])} "
            f"({i['percentual']:.0f}%)"
            for i in itens
        ],
        "- Nenhum limite definido.",
    )

    linhas_metas = []
    for meta in repo.listar_metas():
        progresso = servico_metas.progresso_da_meta(meta, hoje)
        linha = (
            f"- {meta['nome']}: {formatar_brl(meta['aportado'])} de {formatar_brl(meta['valor_alvo'])} "
            f"({progresso['percentual']:.0f}%)"
        )
        if meta["prazo"]:
            linha += f", prazo {meta['prazo']:%d/%m/%Y}"
        if meta["percentual_entrada"] > 0:
            linha += f", separar {meta['percentual_entrada']:g}% de cada entrada"
        linhas_metas.append(linha)
    texto += _secao("METAS DE RESERVA", linhas_metas, "- Nenhuma meta criada.")

    texto += _secao(
        "ALERTAS ATIVOS (regras do app)",
        [f"- [{a.nivel}] {a.titulo}: {a.mensagem}" for a in gerar_alertas(hoje)],
        "- Nenhum alerta.",
    )

    return "\n".join(texto)