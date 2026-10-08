import os

os.environ["DB_NAME"] = "financeiro_teste"  # antes de importar qualquer coisa de src

import pytest

from src.database.connection import get_cursor

TABELAS = ["aportes_meta", "orcamentos", "transacoes", "metas", "contas", "categorias"]


@pytest.fixture
def banco_limpo():
    assert os.environ["DB_NAME"].endswith("_teste"), "Os testes só podem rodar no banco de teste!"
    with get_cursor() as cur:
        for tabela in TABELAS:
            cur.execute(f"DELETE FROM {tabela}")
    yield