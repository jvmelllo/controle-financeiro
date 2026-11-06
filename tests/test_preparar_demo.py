from scripts.preparar_demo import BANCO_DEMO, SCHEMA, comandos_do_schema, preparar_banco


class CursorFalso:
    def __init__(self, eventos):
        self.eventos = eventos

    def execute(self, comando):
        self.eventos.append(comando)

    def close(self):
        self.eventos.append("cursor.close")


class ConexaoFalsa:
    def __init__(self):
        self.eventos = []

    def cursor(self):
        return CursorFalso(self.eventos)

    def commit(self):
        self.eventos.append("commit")


def test_schema_vira_um_comando_por_tabela():
    comandos = comandos_do_schema(SCHEMA.read_text(encoding="utf-8"))
    assert len(comandos) == 6
    for comando in comandos:
        assert comando.startswith("CREATE TABLE IF NOT EXISTS ")
        assert ";" not in comando
        assert "--" not in comando


def test_comentarios_saem_e_o_resto_do_comando_fica():
    texto = """
CREATE TABLE a (
    id INT,           -- ex.: um comentário
    valor BIGINT NOT NULL  -- em centavos
) ENGINE=InnoDB;

create table b (id INT) ENGINE=InnoDB;
"""
    a, b = comandos_do_schema(texto)
    assert a.startswith("CREATE TABLE IF NOT EXISTS a (")
    assert "id INT," in a and "valor BIGINT NOT NULL" in a and "comentário" not in a
    assert b == "CREATE TABLE IF NOT EXISTS b (id INT) ENGINE=InnoDB"


def test_preparar_cria_o_banco_usa_o_banco_e_aplica_o_schema():
    conexao = ConexaoFalsa()
    preparar_banco(conexao, ["CREATE TABLE IF NOT EXISTS a (id INT)", "CREATE TABLE IF NOT EXISTS b (id INT)"])
    assert conexao.eventos == [
        f"CREATE DATABASE IF NOT EXISTS {BANCO_DEMO} CHARACTER SET utf8mb4",
        f"USE {BANCO_DEMO}",
        "CREATE TABLE IF NOT EXISTS a (id INT)",
        "CREATE TABLE IF NOT EXISTS b (id INT)",
        "commit",
        "cursor.close",
    ]


def test_so_o_banco_de_demonstracao_e_tocado():
    assert BANCO_DEMO.endswith("_demo")
