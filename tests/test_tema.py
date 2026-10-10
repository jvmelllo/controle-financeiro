"""Garante que o tema (config.toml) e as cores do código (src/utils/tema.py) continuam combinando."""

import tomllib
from pathlib import Path

from src.services.orcamento import situacao_do_percentual
from src.utils import tema

CONFIG = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"


def _temas() -> dict:
    with open(CONFIG, "rb") as arquivo:
        return tomllib.load(arquivo)["theme"]


def _rgb(cor: str) -> tuple[int, ...]:
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))


def _luminancia(rgb: tuple[int, ...]) -> float:
    def canal(valor: int) -> float:
        valor /= 255
        return valor / 12.92 if valor <= 0.03928 else ((valor + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(cor_a: tuple[int, ...], cor_b: tuple[int, ...]) -> float:
    claro, escuro = sorted((_luminancia(cor_a), _luminancia(cor_b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


def _sobre_o_fundo(cor: str, fundo: str, opacidade: float) -> tuple[int, ...]:
    return tuple(
        round(c * opacidade + f * (1 - opacidade)) for c, f in zip(_rgb(cor), _rgb(fundo))
    )


def test_os_dois_modos_existem_no_config():
    assert {"light", "dark"} <= set(_temas())


def test_azul_de_destaque_e_o_mesmo_no_config_e_no_codigo():
    for modo in ("light", "dark"):
        assert _temas()[modo]["primaryColor"].upper() == tema.AZUL.upper()
        assert _temas()[modo]["blueColor"].upper() == tema.AZUL.upper()


def test_texto_das_caixas_azuis_e_legivel_nos_dois_modos():
    # O Streamlit desenha o fundo da caixa com a cor azul a 20% (escuro) ou 10% (claro) de opacidade.
    for modo, opacidade in (("dark", 0.20), ("light", 0.10)):
        config = _temas()[modo]
        fundo_da_caixa = _sobre_o_fundo(config["blueColor"], config["backgroundColor"], opacidade)
        assert _contraste(_rgb(config["blueTextColor"]), fundo_da_caixa) >= 7  # nível AAA


def test_texto_principal_e_legivel_nos_dois_modos():
    for modo in ("light", "dark"):
        config = _temas()[modo]
        assert _contraste(_rgb(config["textColor"]), _rgb(config["backgroundColor"])) >= 7


def test_paleta_dos_graficos_nao_tem_vermelho():
    for cor in tema.PALETA + _temas()["dark"]["chartCategoricalColors"]:
        r, g, b = _rgb(cor)
        assert not (r > 180 and g < 110 and b < 110), f"{cor} parece vermelho"


def test_cor_de_cada_situacao_do_orcamento():
    assert tema.COR_DA_SITUACAO[situacao_do_percentual(10)] == tema.VERDE
    assert tema.COR_DA_SITUACAO[situacao_do_percentual(85)] == tema.AMARELO
    assert tema.COR_DA_SITUACAO[situacao_do_percentual(120)] == tema.VERMELHO


def test_azul_com_transparencia():
    assert tema.azul_rgba(0.5) == "rgba(34, 128, 243, 0.5)"
