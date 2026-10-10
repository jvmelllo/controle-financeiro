import plotly.graph_objects as go

from src.utils.datas import rotulo_mes
from src.utils.tema import AZUL, CINZA, PALETA, VERDE, VERMELHO, azul_rgba

# ---- Aparência: mude aqui para customizar todos os gráficos ----
# (as cores ficam em src/utils/tema.py; o azul de destaque também está em .streamlit/config.toml)
COR_ENTRADA = VERDE
COR_SAIDA = VERMELHO
COR_SALDO = AZUL
COR_RESULTADO = CINZA
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
            x=valores[::-1], y=nomes[::-1], orientation="h", marker_color=AZUL,
            hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
        ))
        fig.update_xaxes(tickprefix="R$ ", tickformat=",.0f")
    else:
        fig = go.Figure(go.Pie(
            labels=nomes, values=valores, hole=0.5, textinfo="percent",
            marker=dict(colors=PALETA),
            hovertemplate="%{label}<br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
        ))
    return _aplicar_estilo(fig)


def entradas_vs_saidas(totais: list[dict], mostrar_resultado: bool = True) -> go.Figure:
    """totais: [{'rotulo': str, 'entradas': c, 'saidas': c, 'resultado': c}, ...] (centavos)."""
    rotulos = [t["rotulo"] for t in totais]
    fig = go.Figure()
    fig.add_bar(
        name="Entradas", x=rotulos, y=[t["entradas"] / 100 for t in totais],
        marker_color=COR_ENTRADA, hovertemplate="R$ %{y:,.2f}<extra>Entradas</extra>",
    )
    fig.add_bar(
        name="Saídas", x=rotulos, y=[t["saidas"] / 100 for t in totais],
        marker_color=COR_SAIDA, hovertemplate="R$ %{y:,.2f}<extra>Saídas</extra>",
    )
    if mostrar_resultado:
        fig.add_scatter(
            name="Resultado", x=rotulos, y=[t["resultado"] / 100 for t in totais],
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
        fillcolor=azul_rgba(0.12),
        hovertemplate="R$ %{y:,.2f}<extra>Saldo</extra>",
    ))
    fig.update_xaxes(type="category")
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f")
    return _aplicar_estilo(fig)

def evolucao_diaria_do_saldo(evolucao: list[dict]) -> go.Figure:
    """evolucao: [{'data': date, 'saldo': centavos}, ...] (saldo ao fim de cada dia)."""
    fig = go.Figure(go.Scatter(
        x=[e["data"] for e in evolucao], y=[e["saldo"] / 100 for e in evolucao],
        mode="lines", line=dict(color=COR_SALDO, width=3, shape="hv"), fill="tozeroy",
        fillcolor=azul_rgba(0.12),
        hovertemplate="%{x|%d/%m/%Y}<br>R$ %{y:,.2f}<extra>Saldo</extra>",
    ))
    fig.update_xaxes(tickformat="%d/%m")
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f")
    return _aplicar_estilo(fig)