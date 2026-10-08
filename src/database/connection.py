import os
from contextlib import contextmanager

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def _config() -> dict:
    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
        "charset": "utf8mb4",
    }
    faltando = [c for c in ("user", "password", "database") if not config[c]]
    if faltando:
        raise RuntimeError(f"Variáveis ausentes no .env: {', '.join(faltando)}")
    return config


def get_connection():
    return mysql.connector.connect(**_config())


@contextmanager
def get_cursor(dictionary: bool = True):
    """Abre conexão e cursor; confirma (commit) se tudo der certo e desfaz (rollback) se der erro."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()