import os

os.environ["DB_NAME"] = "financeiro_teste"  # antes de importar qualquer coisa de src

import pytest

from src.database.connection import get_cursor
from src.utils import configuracao

HOSTS_LOCAIS = {"localhost", "127.0.0.1", "::1"}

# Variáveis DB_* definidas no terminal valem mais que o .env. Se sobrou alguma apontando para
# a demonstração na nuvem, os testes rodariam no servidor errado: melhor parar logo no início.
if configuracao.ler("DB_HOST", "localhost") not in HOSTS_LOCAIS:
    pytest.exit(
        "Os testes só rodam no MySQL do seu computador, mas DB_HOST aponta para outro servidor "
        "(provavelmente sobrou do passo da demonstração). Feche este terminal e abra outro, ou "
        "limpe as variáveis: Remove-Item Env:DB_HOST, Env:DB_PORT, Env:DB_USER, Env:DB_PASSWORD",
        returncode=2,
    )

TABELAS = ["aportes_meta", "orcamentos", "transacoes", "metas", "contas", "categorias"]


@pytest.fixture
def banco_limpo():
    assert os.environ["DB_NAME"].endswith("_teste"), "Os testes só podem rodar no banco de teste!"
    with get_cursor() as cur:
        for tabela in TABELAS:
            cur.execute(f"DELETE FROM {tabela}")
    yield
