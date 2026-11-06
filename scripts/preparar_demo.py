"""Prepara o banco de demonstração do zero: cria o banco, as tabelas e os dados fictícios.

Uso, com DB_HOST, DB_PORT, DB_USER e DB_PASSWORD definidos no terminal ou no .env:

    python -m scripts.preparar_demo

Serve para o banco da demonstração online (por exemplo no TiDB Cloud), mas funciona em qualquer
MySQL. Só mexe no banco financeiro_demo, nunca no real, e pode ser repetido: as tabelas que já
existem são mantidas e os dados fictícios são gerados de novo.
"""

import os
import re
import sys
from pathlib import Path

import mysql.connector

BANCO_DEMO = "financeiro_demo"
SCHEMA = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"


def comandos_do_schema(texto: str) -> list[str]:
    """Quebra o schema.sql em comandos, sem os comentários, deixando o CREATE TABLE repetível."""
    sem_comentarios = re.sub(r"--[^\n]*", "", texto)
    comandos = [c.strip() for c in sem_comentarios.split(";") if c.strip()]
    return [
        re.sub(r"^CREATE TABLE\s+", "CREATE TABLE IF NOT EXISTS ", c, flags=re.IGNORECASE)
        for c in comandos
    ]


def preparar_banco(conexao, comandos: list[str]) -> None:
    """Cria o banco de demonstração (se não existir) e aplica os comandos do schema nele."""
    cursor = conexao.cursor()
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {BANCO_DEMO} CHARACTER SET utf8mb4")
        cursor.execute(f"USE {BANCO_DEMO}")
        for comando in comandos:
            cursor.execute(comando)
        conexao.commit()
    finally:
        cursor.close()


def main() -> int:
    os.environ["DB_NAME"] = BANCO_DEMO  # antes de importar o resto: nunca o banco real

    from src.database import connection
    from src.utils import configuracao

    if configuracao.modo_demo():
        print("MODO_DEMO está ligado, e ele só permite leitura. Desligue-o (tire do .env) para preparar o banco.")
        return 1

    config = connection._config()
    config.pop("database")  # o banco ainda pode não existir
    conexao = mysql.connector.connect(**config)
    try:
        preparar_banco(conexao, comandos_do_schema(SCHEMA.read_text(encoding="utf-8")))
    finally:
        conexao.close()
    print(f"Banco {BANCO_DEMO} e tabelas prontos em {config['host']}.")

    from scripts import gerar_dados_demo

    gerar_dados_demo.limpar()
    quantidade = gerar_dados_demo.gerar()
    print(f"Dados fictícios gerados: {quantidade} transações, orçamentos e metas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
