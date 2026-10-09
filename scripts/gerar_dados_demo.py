#o script força o financeiro_demo (ignora o .env) e tem uma trava, então é impossível ele apagar o banco real por engano. 
#A semente fixa faz os dados serem sempre os mesmos
import os

os.environ["DB_NAME"] = "financeiro_demo"  # garante que o banco real nunca é tocado

import calendar
import random
from datetime import date

from src.database import repositories as repo
from src.database.connection import get_cursor

TABELAS = ["aportes_meta", "orcamentos", "transacoes", "metas", "contas", "categorias"]
SEMENTE = 2026
FORMAS = ["pix", "debito", "credito", "dinheiro"]

CATEGORIAS = {
    "entrada": ["Chronomax", "Freelas", "Outras entradas"],
    "saida": ["Alimentação", "Transporte", "Lazer", "Compras", "Estudos",
              "Assinaturas", "Saúde", "Presentes"],
}

# categoria: (mín. de lançamentos no mês, máx., valor mín., valor máx.) em centavos
VARIAVEIS = {
    "Alimentação": (10, 16, 1500, 6500),
    "Transporte": (8, 14, 500, 2500),
    "Lazer": (3, 5, 2000, 9000),
    "Compras": (1, 2, 5000, 25000),
    "Estudos": (0, 2, 3000, 12000),
    "Saúde": (0, 1, 2000, 8000),
    "Presentes": (0, 1, 3000, 15000),
}


def limpar() -> None:
    with get_cursor() as cur:
        for tabela in TABELAS:
            cur.execute(f"DELETE FROM {tabela}")


def ultimos_meses(qtd: int = 6, hoje: date | None = None) -> list[tuple[int, int]]:
    hoje = hoje or date.today()
    ano, mes = hoje.year, hoje.month
    meses = []
    for _ in range(qtd):
        meses.append((ano, mes))
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
    return list(reversed(meses))


def gerar() -> int:
    rng = random.Random(SEMENTE)
    hoje = date.today()
    total = 0

    conta = repo.criar_conta("Conta corrente", "corrente", saldo_inicial=80000)
    repo.criar_conta("Carteira", "carteira", saldo_inicial=5000)
    cats = {
        nome: repo.criar_categoria(nome, tipo)
        for tipo, nomes in CATEGORIAS.items()
        for nome in nomes
    }

    def lancar(dia, valor, tipo, categoria, descricao, forma):
        nonlocal total
        if dia <= hoje:  # nada de lançamentos no futuro
            repo.inserir_transacao(dia, valor, tipo, cats[categoria], conta, descricao, forma)
            total += 1

    for ano, mes in ultimos_meses():
        dias = calendar.monthrange(ano, mes)[1]
        fins_de_semana = [
            date(ano, mes, d) for d in range(1, dias + 1) if date(ano, mes, d).weekday() >= 5
        ]

        # entradas irregulares: eventos nos fins de semana + um freela ocasional
        for dia in rng.sample(fins_de_semana, k=rng.randint(3, 7)):
            lancar(dia, rng.randrange(20000, 45001, 500), "entrada", "Chronomax",
                   "Evento esportivo", "pix")
        if rng.random() < 0.3:
            lancar(date(ano, mes, rng.randint(1, dias)), rng.randrange(10000, 30001, 500),
                   "entrada", "Freelas", "Trabalho avulso", "pix")

        # gastos fixos
        lancar(date(ano, mes, 5), 3990, "saida", "Assinaturas", "Streaming", "credito")
        lancar(date(ano, mes, 10), 2190, "saida", "Assinaturas", "Música", "credito")
        lancar(date(ano, mes, 15), 5500, "saida", "Assinaturas", "Celular", "debito")

        # gastos variáveis
        for categoria, (qmin, qmax, vmin, vmax) in VARIAVEIS.items():
            for _ in range(rng.randint(qmin, qmax)):
                lancar(date(ano, mes, rng.randint(1, dias)), rng.randrange(vmin, vmax + 1, 50),
                       "saida", categoria, None, rng.choice(FORMAS))
    return total


if __name__ == "__main__":
    assert os.environ["DB_NAME"].endswith("_demo"), "Este script só pode rodar no banco demo!"
    limpar()
    quantidade = gerar()
    print(f"Dados fictícios gerados em {os.environ['DB_NAME']}: {quantidade} transações.")