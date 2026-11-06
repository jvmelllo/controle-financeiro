import re
from contextlib import contextmanager

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import errors as mysql_errors

from src.utils import configuracao

load_dotenv()

MENSAGEM_SOMENTE_LEITURA = (
    "Esta demonstração é somente leitura: nada é salvo, editado nem excluído. "
    "Rode o projeto no seu computador para usar de verdade."
)
# 1792: tentativa de escrever dentro de uma transação somente leitura.
# 1142: o usuário do banco não tem permissão de escrita nessa tabela.
ERROS_DE_ESCRITA_NEGADA = {1792, 1142}

_COMANDOS_DE_LEITURA = {"SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"}
_COMENTARIOS_SQL = re.compile(r"/\*.*?\*/|--[^\n]*", re.DOTALL)


class ModoDemonstracao(ValueError):
    """Tentativa de gravar dados enquanto o app roda como demonstração (somente leitura).

    É um ValueError de propósito: as telas já mostram a mensagem de qualquer ValueError
    vindo das operações de gravação, sem precisar de um tratamento à parte.
    """


def _exigir_leitura(sql) -> None:
    """Recusa qualquer comando que não seja uma consulta (ou que traga mais de um comando).

    Uma segunda trava, no Python, porque nem todo servidor respeita a transação somente leitura:
    o TiDB, por exemplo, aceita a sintaxe mas continua permitindo gravar.
    """
    texto = _COMENTARIOS_SQL.sub(" ", str(sql)).strip().lstrip("(").lstrip()
    corpo = texto.rstrip(";").rstrip()
    palavras = corpo.split(None, 1)
    if not palavras or palavras[0].upper() not in _COMANDOS_DE_LEITURA or ";" in corpo:
        raise ModoDemonstracao(MENSAGEM_SOMENTE_LEITURA)


class _CursorSomenteLeitura:
    """Cursor do modo demonstração: só deixa passar consultas; o resto vai direto ao cursor real."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, operacao, *args, **kwargs):
        _exigir_leitura(operacao)
        return self._cursor.execute(operacao, *args, **kwargs)

    def executemany(self, operacao, *args, **kwargs):
        _exigir_leitura(operacao)
        return self._cursor.executemany(operacao, *args, **kwargs)

    def __getattr__(self, nome):
        return getattr(self._cursor, nome)


def _config() -> dict:
    config = {
        "host": configuracao.ler("DB_HOST", "localhost"),
        "port": int(configuracao.ler("DB_PORT", "3306")),
        "user": configuracao.ler("DB_USER"),
        "password": configuracao.ler("DB_PASSWORD"),
        "database": configuracao.ler("DB_NAME"),
        "charset": "utf8mb4",
    }
    faltando = [c for c in ("user", "password", "database") if not config[c]]
    if faltando:
        raise RuntimeError(f"Configuração ausente (.env ou segredos): {', '.join(faltando)}")
    if configuracao.modo_demo() and not config["database"].endswith("_demo"):
        # trava contra publicar os dados reais por engano
        raise RuntimeError("No modo demonstração só é permitido um banco que termine em _demo.")
    certificado = configuracao.ler("DB_SSL_CA")  # opcional: confere o certificado do servidor (TLS)
    if certificado:
        config["ssl_ca"] = certificado
        config["ssl_verify_cert"] = True
    return config


def get_connection():
    return mysql.connector.connect(**_config())


@contextmanager
def get_cursor(dictionary: bool = True):
    """Abre conexão e cursor; confirma (commit) se tudo der certo e desfaz (rollback) se der erro.

    No modo demonstração nada é gravado, por duas travas: a transação é somente leitura (o MySQL
    recusa INSERT, UPDATE e DELETE) e o cursor só aceita consultas, mesmo que alguma tela tente gravar.
    """
    somente_leitura = configuracao.modo_demo()
    conn = get_connection()
    try:
        if somente_leitura:
            conn.start_transaction(readonly=True)
        cursor = conn.cursor(dictionary=dictionary)
        try:
            yield _CursorSomenteLeitura(cursor) if somente_leitura else cursor
            conn.commit()
        except mysql_errors.Error as erro:
            conn.rollback()
            if somente_leitura and erro.errno in ERROS_DE_ESCRITA_NEGADA:
                raise ModoDemonstracao(MENSAGEM_SOMENTE_LEITURA) from erro
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    finally:
        conn.close()
