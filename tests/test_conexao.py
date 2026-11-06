import pytest
from mysql.connector import errors

from src.database import connection
from src.utils import configuracao


class CursorFalso:
    lastrowid = 7

    def __init__(self, eventos):
        self.eventos = eventos

    def execute(self, operacao, params=None):
        self.eventos.append(("execute", operacao.strip().split()[0].upper()))

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


def test_modo_demo_cursor_deixa_passar_consultas(monkeypatch):
    conexao = _preparar(monkeypatch, demo=True)
    with connection.get_cursor() as cur:
        cur.execute("SELECT id FROM contas WHERE id = %s", (1,))
        assert cur.lastrowid == 7  # o resto do cursor real continua acessível
    assert ("execute", "SELECT") in conexao.eventos


def test_modo_demo_cursor_barra_gravacao_antes_de_chegar_ao_banco(monkeypatch):
    # o TiDB ignora a transação somente leitura, então esta trava precisa funcionar sozinha
    conexao = _preparar(monkeypatch, demo=True)
    with pytest.raises(connection.ModoDemonstracao, match="somente leitura"):
        with connection.get_cursor() as cur:
            cur.execute("DELETE FROM transacoes")
    assert not any(e[0] == "execute" for e in conexao.eventos if isinstance(e, tuple))
    assert "rollback" in conexao.eventos
    assert conexao.eventos[-1] == "conn.close"


def test_fora_do_modo_demo_o_cursor_nao_e_filtrado(monkeypatch):
    conexao = _preparar(monkeypatch, demo=False)
    with connection.get_cursor() as cur:
        cur.execute("INSERT INTO contas (nome) VALUES (%s)", ("x",))
    assert ("execute", "INSERT") in conexao.eventos


def test_consultas_passam_pela_trava():
    for sql in (
        "SELECT 1",
        "  select * from contas",
        "\n    SELECT id\n    FROM contas WHERE x = %s\n",
        "(SELECT 1) UNION (SELECT 2)",
        "/* comentario */ SELECT 1",
        "-- comentario\nSELECT 1",
        "SELECT 1;",
        "SHOW TABLES",
        "DESCRIBE contas",
        "EXPLAIN SELECT 1",
    ):
        connection._exigir_leitura(sql)  # não pode levantar


def test_gravacoes_e_comandos_estranhos_nao_passam_pela_trava():
    for sql in (
        "INSERT INTO contas (nome) VALUES ('x')",
        "  update contas set nome = 'x'",
        "DELETE FROM contas",
        "REPLACE INTO contas (id) VALUES (1)",
        "INSERT IGNORE INTO contas (id) VALUES (1)",
        "TRUNCATE TABLE contas",
        "DROP TABLE contas",
        "ALTER TABLE contas ADD x INT",
        "CREATE TABLE x (id INT)",
        "SET autocommit = 1",
        "WITH t AS (SELECT 1) DELETE FROM contas",
        "/* SELECT */ DELETE FROM contas",
        "SELECT 1; DELETE FROM contas",
        "",
        "   ",
    ):
        with pytest.raises(connection.ModoDemonstracao):
            connection._exigir_leitura(sql)


def test_modo_demonstracao_e_um_value_error():
    # as telas já tratam ValueError nas gravações e mostram a mensagem sem quebrar
    assert issubclass(connection.ModoDemonstracao, ValueError)


def test_servidor_que_recusa_transacao_somente_leitura_continua_funcionando(monkeypatch):
    # o TiDB não aceita "SET TRANSACTION READ ONLY"; o app não pode quebrar por isso
    conexao = _preparar(monkeypatch, demo=True)

    def recusar(**opcoes):
        raise errors.ProgrammingError(msg="não suportado", errno=1105)

    conexao.start_transaction = recusar
    with connection.get_cursor() as cur:
        cur.execute("SELECT 1")
    assert ("execute", "SELECT") in conexao.eventos
    assert conexao.eventos[-3:] == ["commit", "cursor.close", "conn.close"]


def test_sem_transacao_somente_leitura_a_trava_de_comandos_segura_as_gravacoes(monkeypatch):
    conexao = _preparar(monkeypatch, demo=True)

    def recusar(**opcoes):
        raise errors.ProgrammingError(msg="não suportado", errno=1105)

    conexao.start_transaction = recusar
    with pytest.raises(connection.ModoDemonstracao):
        with connection.get_cursor() as cur:
            cur.execute("DELETE FROM transacoes")
    assert not any(e[0] == "execute" for e in conexao.eventos if isinstance(e, tuple))
    assert conexao.eventos[-1] == "conn.close"


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


def test_certificado_so_entra_se_for_configurado(monkeypatch):
    _ambiente(monkeypatch)
    monkeypatch.delenv("DB_SSL_CA", raising=False)
    assert "ssl_ca" not in connection._config()
    monkeypatch.setenv("DB_SSL_CA", "/etc/ssl/certs/ca-certificates.crt")
    config = connection._config()
    assert config["ssl_ca"] == "/etc/ssl/certs/ca-certificates.crt"
    assert config["ssl_verify_cert"] is True


def test_fora_do_modo_demo_qualquer_banco_vale(monkeypatch):
    _ambiente(monkeypatch, banco="financeiro", demo=False)
    assert connection._config()["database"] == "financeiro"
