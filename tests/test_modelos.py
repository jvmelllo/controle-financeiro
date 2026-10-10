from src.assistant import modelos


def test_catalogo_tem_nomes_unicos_e_destaques():
    nomes = [m.nome for m in modelos.CATALOGO]
    assert len(nomes) == len(set(nomes))
    assert modelos.MODELO_PADRAO == nomes[0]
    assert sum(m.destaque for m in modelos.CATALOGO) >= 2


def test_recomendacao_acompanha_a_memoria():
    assert modelos.recomendar(None).nome == "qwen2.5:3b"  # sem informação: o mais leve
    assert modelos.recomendar(4).nome == "qwen2.5:3b"
    assert modelos.recomendar(7.8).nome == "qwen2.5:3b"
    assert modelos.recomendar(8).nome == "qwen2.5:3b"
    assert modelos.recomendar(15.7).nome == "qwen2.5:7b"  # "16 GB" aparece como ~15,7
    assert modelos.recomendar(32).nome == "qwen2.5:7b"


def test_comando_de_instalacao():
    assert modelos.comando_de_instalacao("qwen2.5:3b") == "ollama pull qwen2.5:3b"


def test_memoria_ram_devolve_numero_plausivel_ou_none():
    ram = modelos.memoria_ram_gb()
    assert ram is None or 0.5 < ram < 4096
