import plotly.graph_objects as go

from src.utils.datas import rotulo_mes

# ---- Aparência: mude aqui para customizar todos os gráficos ----
COR_ENTRADA = "#2E9E6B"
COR_SAIDA = "#D64545"
COR_SALDO = "#3B6FD4"
COR_RESULTADO = "#6B7280"
TEMPLATE = "plotly_white"
ALTURA = 380


def _aplicar_estilo(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        template=TEMPLATE,
        height=ALTURA,
        separators=",.",  # formato brasileiro: 1.234,56
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def gastos_por_categoria(gastos: list[dict], formato: str = "rosca") -> go.Figure:
    """gastos: [{'categoria': str, 'total': centavos}, ...] já em ordem decrescente."""
    nomes = [g["categoria"] for g in gastos]
    valores = [g["total"] / 100 for g in gastos]

    if formato == "barras":
        fig = go.Figure(go.Bar(
            x=valores[::-1], y=nomes[::-1], orientation="h", marker_color=COR_SAIDA,
            hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
        ))
        fig.update_xaxes(tickprefix="R$ ", tickformat=",.0f")
    else:
        fig = go.Figure(go.Pie(
            labels=nomes, values=valores, hole=0.5, textinfo="percent",
            hovertemplate="%{label}<br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
        ))
    return _aplicar_estilo(fig)


def entradas_vs_saidas(totais: list[dict]) -> go.Figure:
    """totais: [{'mes': 'AAAA-MM', 'entradas': c, 'saidas': c, 'resultado': c}, ...]."""
    meses = [rotulo_mes(t["mes"]) for t in totais]
    fig = go.Figure()
    fig.add_bar(
        name="Entradas", x=meses, y=[t["entradas"] / 100 for t in totais],
        marker_color=COR_ENTRADA, hovertemplate="R$ %{y:,.2f}<extra>Entradas</extra>",
    )
    fig.add_bar(
        name="Saídas", x=meses, y=[t["saidas"] / 100 for t in totais],
        marker_color=COR_SAIDA, hovertemplate="R$ %{y:,.2f}<extra>Saídas</extra>",
    )
    fig.add_scatter(
        name="Resultado", x=meses, y=[t["resultado"] / 100 for t in totais],
        mode="lines+markers", line=dict(color=COR_RESULTADO, dash="dot"),
        hovertemplate="R$ %{y:,.2f}<extra>Resultado</extra>",
    )
    fig.update_layout(barmode="group")
    fig.update_xaxes(type="category")
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f")
    return _aplicar_estilo(fig)


def evolucao_do_saldo(evolucao: list[dict]) -> go.Figure:
    """evolucao: [{'mes': 'AAAA-MM', 'saldo': centavos}, ...] (saldo ao fim de cada mês)."""
    meses = [rotulo_mes(e["mes"]) for e in evolucao]
    fig = go.Figure(go.Scatter(
        x=meses, y=[e["saldo"] / 100 for e in evolucao], mode="lines+markers",
        line=dict(color=COR_SALDO, width=3), fill="tozeroy",
        fillcolor="rgba(59, 111, 212, 0.12)",
        hovertemplate="R$ %{y:,.2f}<extra>Saldo</extra>",
    ))
    fig.update_xaxes(type="category")
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f")
    return _aplicar_estilo(fig)