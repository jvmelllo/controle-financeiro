import pytest
from mysql.connector import errors

from src.database import connection
from src.utils import configuracao


class CursorFalso:
    def __init__(self, eventos):
        self.eventos = eventos

    def close(self):
        self.eventos.append("cursor.close")


class ConexaoFalsa:
    """Registra o que o gerenciador de contexto faz com a conexão, sem abrir nada de verdade."""

    def __init__(self):
        self.eventos = []

    def start_transaction(self, **opcoes):
        self.eventos.append(("start_transaction", opcoes))

    def cursor(self, dictionary=True):
        self.eventos.append(("cursor", dictionary))
        return CursorFalso(self.eventos)

    def commit(self):
        self.eventos.append("commit")

    def rollback(self):
        self.eventos.append("rollback")

    def close(self):
        self.eventos.append("conn.close")


def _preparar(monkeypatch, demo: bool) -> ConexaoFalsa:
    conexao = ConexaoFalsa()
    monkeypatch.setattr(configuracao, "_segredo", lambda nome: None)
    monkeypatch.setattr(connection, "get_connection", lambda: conexao)
    if demo:
        monkeypatch.setenv("MODO_DEMO", "1")
    else:
        monkeypatch.delenv("MODO_DEMO", raising=False)
    return conexao


def _erro_mysql(numero: int) -> errors.DatabaseError:
    return errors.DatabaseError(msg=f"erro {numero}", errno=numero)


# ---------- uso normal (computador) ----------
def test_fora_do_modo_demo_confirma_e_fecha_tudo(monkeypatch):
    conexao = _preparar(monkeypatch, demo=False)
    with connection.get_cursor():
        pass
    assert conexao.eventos == [("cursor", True), "commit", "cursor.close", "conn.close"]


def test_fora_do_modo_demo_nao_abre_transacao_somente_leitura(monkeypatch):
    conexao = _preparar(monkeypatch, demo=False)
    with connection.get_cursor():
        pass
    assert not any(e[0] == "start_transaction" for e in conexao.eventos if isinstance(e, tuple))


def test_erro_desfaz_e_propaga_o_erro_original(monkeypatch):
    conexao = _preparar(monkeypatch, demo=False)
    with pytest.raises(KeyError):
        with connection.get_cursor():
            raise KeyError("x")
    assert "rollback" in conexao.eventos
    assert "commit" not in conexao.eventos
    assert conexao.eventos[-2:] == ["cursor.close", "conn.close"]


def test_erro_de_escrita_do_mysql_fora_do_modo_demo_nao_e_traduzido(monkeypatch):
    _preparar(monkeypatch, demo=False)
    with pytest.raises(errors.DatabaseError):
        with connection.get_cursor():
            raise _erro_mysql(1792)


# ---------- modo demonstração ----------
def test_modo_demo_abre_transacao_somente_leitura_antes_do_cursor(monkeypatch):
    conexao = _preparar(monkeypatch, demo=True)
    with connection.get_cursor():
        pass
    assert conexao.eventos[0] == ("start_transaction", {"readonly": True})
    assert conexao.eventos[1] == ("cursor", True)
    assert conexao.eventos[-3:] == ["commit", "cursor.close", "conn.close"]


def test_modo_demo_traduz_escrita_recusada_pela_transacao(monkeypatch):
    conexao = _preparar(monkeypatch, demo=True)
    with pytest.raises(connection.ModoDemonstracao, match="somente leitura"):
        with connection.get_cursor():
            raise _erro_mysql(1792)
    assert "rollback" in conexao.eventos
    assert conexao.eventos[-1] == "conn.close"


def test_modo_demo_traduz_escrita_negada_por_permissao(monkeypatch):
    _preparar(monkeypatch, demo=True)
    with pytest.raises(connection.ModoDemonstracao):
        with connection.get_cursor():
            raise _erro_mysql(1142)


def test_modo_demo_nao_traduz_outros_erros_do_mysql(monkeypatch):
    _preparar(monkeypatch, demo=True)
    with pytest.raises(errors.DatabaseError):
        with connection.get_cursor():
            raise _erro_mysql(1064)


def test_modo_demonstracao_e_um_value_error():
    # as telas já tratam ValueError nas gravações e mostram a mensagem sem quebrar
    assert issubclass(connection.ModoDemonstracao, ValueError)


def test_conexao_fecha_mesmo_se_a_transacao_nao_abrir(monkeypatch):
    conexao = _preparar(monkeypatch, demo=True)

    def falhar(**opcoes):
        raise _erro_mysql(1568)

    conexao.start_transaction = falhar
    with pytest.raises(errors.DatabaseError):
        with connection.get_cursor():
            pass
    assert conexao.eventos == ["conn.close"]


# ---------- configuração da conexão ----------
def _ambiente(monkeypatch, banco="financeiro_demo", demo=False):
    monkeypatch.setattr(configuracao, "_segredo", lambda nome: None)
    monkeypatch.setenv("DB_HOST", "servidor.exemplo")
    monkeypatch.setenv("DB_PORT", "12345")
    monkeypatch.setenv("DB_USER", "usuario")
    monkeypatch.setenv("DB_PASSWORD", "senha-de-teste")
    monkeypatch.setenv("DB_NAME", banco)
    if demo:
        monkeypatch.setenv("MODO_DEMO", "1")
    else:
        monkeypatch.delenv("MODO_DEMO", raising=False)


def test_config_le_o_ambiente(monkeypatch):
    _ambiente(monkeypatch)
    config = connection._config()
    assert config["host"] == "servidor.exemplo"
    assert config["port"] == 12345
    assert config["user"] == "usuario"
    assert config["database"] == "financeiro_demo"
    assert config["charset"] == "utf8mb4"


def test_config_aceita_os_segredos_do_streamlit(monkeypatch):
    _ambiente(monkeypatch)
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.setattr(configuracao, "_segredo", lambda nome: "nuvem.exemplo" if nome == "DB_HOST" else None)
    assert connection._config()["host"] == "nuvem.exemplo"


def test_config_avisa_o_que_esta_faltando(monkeypatch):
    _ambiente(monkeypatch)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="password"):
        connection._config()


def test_modo_demo_so_aceita_banco_terminado_em_demo(monkeypatch):
    _ambiente(monkeypatch, banco="financeiro", demo=True)
    with pytest.raises(RuntimeError, match="_demo"):
        connection._config()


def test_modo_demo_aceita_o_banco_demo(monkeypatch):
    _ambiente(monkeypatch, banco="financeiro_demo", demo=True)
    assert connection._config()["database"] == "financeiro_demo"


def test_fora_do_modo_demo_qualquer_banco_vale(monkeypatch):
    _ambiente(monkeypatch, banco="financeiro", demo=False)
    assert connection._config()["database"] == "financeiro"
