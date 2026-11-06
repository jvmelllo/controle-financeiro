import streamlit as st

from src.utils import configuracao


def _sem_segredos(monkeypatch):
    """Os testes não podem depender de um .streamlit/secrets.toml que exista na máquina."""
    monkeypatch.setattr(configuracao, "_segredo", lambda nome: None)


def test_ler_devolve_a_variavel_de_ambiente(monkeypatch):
    _sem_segredos(monkeypatch)
    monkeypatch.setenv("TESTE_CONFIG", "valor")
    assert configuracao.ler("TESTE_CONFIG") == "valor"


def test_ler_usa_o_padrao_quando_nao_existe(monkeypatch):
    _sem_segredos(monkeypatch)
    monkeypatch.delenv("TESTE_CONFIG", raising=False)
    assert configuracao.ler("TESTE_CONFIG") is None
    assert configuracao.ler("TESTE_CONFIG", "padrao") == "padrao"


def test_ler_trata_valor_vazio_como_ausente(monkeypatch):
    _sem_segredos(monkeypatch)
    monkeypatch.setenv("TESTE_CONFIG", "")
    assert configuracao.ler("TESTE_CONFIG", "padrao") == "padrao"


def test_ler_cai_nos_segredos_do_streamlit(monkeypatch):
    monkeypatch.delenv("TESTE_CONFIG", raising=False)
    monkeypatch.setattr(configuracao, "_segredo", lambda nome: "da-nuvem")
    assert configuracao.ler("TESTE_CONFIG") == "da-nuvem"


def test_variavel_de_ambiente_vale_mais_que_o_segredo(monkeypatch):
    monkeypatch.setattr(configuracao, "_segredo", lambda nome: "da-nuvem")
    monkeypatch.setenv("TESTE_CONFIG", "do-terminal")
    assert configuracao.ler("TESTE_CONFIG") == "do-terminal"


def test_segredo_converte_para_texto(monkeypatch):
    monkeypatch.setattr(st, "secrets", {"DB_PORT": 3306})
    assert configuracao._segredo("DB_PORT") == "3306"
    assert configuracao._segredo("OUTRO") is None


def test_segredo_sem_arquivo_de_segredos_devolve_none(monkeypatch):
    class SemArquivo:
        def get(self, nome):
            raise FileNotFoundError("sem secrets.toml")

    monkeypatch.setattr(st, "secrets", SemArquivo())
    assert configuracao._segredo("DB_PORT") is None


def test_modo_demo_vem_desligado(monkeypatch):
    _sem_segredos(monkeypatch)
    monkeypatch.delenv("MODO_DEMO", raising=False)
    assert configuracao.modo_demo() is False


def test_modo_demo_liga_com_valores_afirmativos(monkeypatch):
    _sem_segredos(monkeypatch)
    for valor in ("1", "true", "TRUE", "sim", " Sim ", "yes", "on"):
        monkeypatch.setenv("MODO_DEMO", valor)
        assert configuracao.modo_demo() is True, valor


def test_modo_demo_continua_desligado_com_outros_valores(monkeypatch):
    _sem_segredos(monkeypatch)
    for valor in ("0", "false", "nao", "", "talvez"):
        monkeypatch.setenv("MODO_DEMO", valor)
        assert configuracao.modo_demo() is False, valor


def test_modo_demo_pode_vir_dos_segredos(monkeypatch):
    monkeypatch.delenv("MODO_DEMO", raising=False)
    monkeypatch.setattr(configuracao, "_segredo", lambda nome: "1" if nome == "MODO_DEMO" else None)
    assert configuracao.modo_demo() is True
