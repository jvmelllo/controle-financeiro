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


# categoria: quanto o limite do mês atual representa do gasto do mês anterior
# (abaixo de 1 aperta o orçamento e mostra o semáforo em atenção ou estourado)
FATOR_DO_LIMITE = {
    "Alimentação": 0.95, "Lazer": 0.90, "Transporte": 1.15, "Compras": 1.30, "Assinaturas": 1.05,
}


def criar_orcamentos(gasto_por_mes: dict, meses: list[tuple[int, int]], cats: dict) -> int:
    """Limites do mês atual, calculados sobre o gasto do mês anterior (arredondado a R$ 10)."""
    anterior, atual = meses[-2], meses[-1]
    criados = 0
    for categoria, fator in FATOR_DO_LIMITE.items():
        base = gasto_por_mes[anterior].get(categoria, 0)
        if base <= 0:
            continue
        limite = max(round(base * fator / 1000) * 1000, 1000)
        repo.definir_orcamento(cats[categoria], f"{atual[0]:04d}-{atual[1]:02d}", limite)
        criados += 1
    return criados


def criar_metas(hoje: date) -> int:
    """Duas metas com contribuições nos últimos meses e uma porcentagem de cada entrada."""
    reserva = repo.criar_meta(
        "Reserva de emergência", 600000, date(hoje.year + 1, hoje.month, 1), percentual_entrada=10
    )
    viagem = repo.criar_meta(
        "Viagem de fim de ano", 250000, date(hoje.year if hoje.month < 12 else hoje.year + 1, 12, 15),
        percentual_entrada=5,
    )
    tres_meses = ultimos_meses(3, hoje)
    contribuicoes = [
        (reserva, date(a, m, 10), valor) for (a, m), valor in zip(tres_meses, (40000, 35000, 50000))
    ] + [
        (viagem, date(a, m, 12), 30000) for a, m in tres_meses[-2:]
    ]
    for meta, data, valor in contribuicoes:
        if data <= hoje:  # nada no futuro
            repo.inserir_aporte(meta, data, valor)
    return 2


def gerar() -> int:
    rng = random.Random(SEMENTE)
    hoje = date.today()
    total = 0
    meses = ultimos_meses(hoje=hoje)
    gasto_por_mes = {mes: {} for mes in meses}

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
            if tipo == "saida":
                por_categoria = gasto_por_mes[(dia.year, dia.month)]
                por_categoria[categoria] = por_categoria.get(categoria, 0) + valor

    for ano, mes in meses:
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

    criar_orcamentos(gasto_por_mes, meses, cats)
    criar_metas(hoje)
    return total


if __name__ == "__main__":
    assert os.environ["DB_NAME"].endswith("_demo"), "Este script só pode rodar no banco demo!"
    limpar()
    quantidade = gerar()
    print(f"Dados fictícios gerados em {os.environ['DB_NAME']}: {quantidade} transações, orçamentos e metas.")