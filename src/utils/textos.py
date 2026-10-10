import unicodedata


def normalizar_texto(texto: str) -> str:
    """'  Alimentação ' -> 'alimentacao' (minúsculas, sem acentos e sem espaços nas pontas).

    Serve para comparar nomes do jeito que o MySQL compara: sem diferenciar acentos nem maiúsculas.
    """
    decomposto = unicodedata.normalize("NFD", texto.strip().casefold())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
