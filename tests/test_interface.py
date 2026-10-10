"""Mantém a interface sóbria: emoji só onde ele chama a atenção para um problema."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⬀-⯿⌀-⏿←-⇿■-◿]")
# Alertas do assistente (🚨 ⚠️ 💡) e marcas de problema na prévia da importação (❌ ⚠️).
PERMITIDOS = set("🚨⚠💡❌")


def _arquivos_de_tela() -> list[Path]:
    return [
        RAIZ / "app.py",
        *sorted((RAIZ / "pages").glob("*.py")),
        *sorted((RAIZ / "src" / "utils").glob("*.py")),
    ]


def test_sem_emoji_decorativo_nas_telas():
    problemas = []
    for arquivo in _arquivos_de_tela():
        for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), start=1):
            if "page_icon=" in linha:
                continue  # ícone da aba do navegador, não aparece na página
            extras = set(EMOJI.findall(linha)) - PERMITIDOS
            if extras:
                problemas.append(f"{arquivo.name}:{numero} {''.join(sorted(extras))}")
    assert not problemas, "Emoji fora do permitido: " + "; ".join(problemas)
