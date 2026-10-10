"""Cores do app em um só lugar (sem depender do Streamlit, para os gráficos poderem usar).

O azul de destaque também aparece em .streamlit/config.toml (primaryColor): se mudar aqui,
mude lá também. Vermelho, amarelo e verde ficam só para quando a cor tem significado
(estourou o limite, atenção, tudo certo).
"""

AZUL = "#2280F3"      # destaque do app (abas, botões, barras, saldo)
VERDE = "#2E9E6B"     # entradas, tudo certo, meta concluída
AMARELO = "#E0A800"   # atenção
VERMELHO = "#D64545"  # saídas, limite estourado
CINZA = "#6B7280"

# Ordem usada nas fatias da rosca de gastos: começa no azul e evita vermelho.
PALETA = [
    "#2280F3", "#7DB8FF", "#29B09D", "#7DEFA1", "#FF8700",
    "#FFD16A", "#6D3FC0", "#B9A2E8", "#9AA5B8", "#0F4FA8",
]

COR_DA_SITUACAO = {"ok": VERDE, "atencao": AMARELO, "estourado": VERMELHO}


def azul_rgba(opacidade: float) -> str:
    """O azul de destaque com transparência, para preenchimentos."""
    return f"rgba(34, 128, 243, {opacidade})"
