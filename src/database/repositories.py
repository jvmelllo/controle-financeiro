from src.database.connection import get_cursor
from src.utils.datas import intervalo_do_mes
from mysql.connector import errors as mysql_errors

TIPOS = ("entrada", "saida")
CAMPOS_EDITAVEIS = {
    "data", "valor", "tipo", "categoria_id", "conta_id", "descricao", "forma_pagamento",
}
TIPOS_CONTA = ("carteira", "corrente", "poupanca", "cartao")


def _nome_valido(nome: str) -> str:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("O nome não pode ficar vazio.")
    return nome


# ---------- validações ----------
def _validar_tipo(tipo: str) -> None:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo inválido: {tipo!r}. Use 'entrada' ou 'saida'.")


def _validar_transacao(cur, valor, tipo, categoria_id) -> None:
    _validar_tipo(tipo)
    if not isinstance(valor, int) or isinstance(valor, bool) or valor <= 0:
        raise ValueError("O valor deve ser um inteiro positivo, em centavos.")
    cur.execute("SELECT tipo FROM categorias WHERE id = %s", (categoria_id,))
    categoria = cur.fetchone()
    if categoria is None:
        raise ValueError("Categoria inexistente.")
    if categoria["tipo"] != tipo:
        raise ValueError(f"A categoria é de {categoria['tipo']}, mas a transação é de {tipo}.")


# ---------- categorias ----------
def criar_categoria(nome: str, tipo: str) -> int:
    _validar_tipo(tipo)
    nome = _nome_valido(nome)
    try:
        with get_cursor() as cur:
            cur.execute("INSERT INTO categorias (nome, tipo) VALUES (%s, %s)", (nome, tipo))
            return cur.lastrowid
    except mysql_errors.IntegrityError:
        raise ValueError(f"Já existe uma categoria chamada '{nome}'.") from None


def listar_categorias(tipo: str | None = None, apenas_ativas: bool = True) -> list[dict]:
    sql = "SELECT id, nome, tipo, ativa FROM categorias WHERE 1 = 1"
    params = []
    if tipo:
        _validar_tipo(tipo)
        sql += " AND tipo = %s"
        params.append(tipo)
    if apenas_ativas:
        sql += " AND ativa = 1"
    sql += " ORDER BY nome"
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# ---------- contas ----------
def criar_conta(nome: str, tipo: str, saldo_inicial: int = 0) -> int:
    nome = _nome_valido(nome)
    if tipo not in TIPOS_CONTA:
        raise ValueError(f"Tipo de conta inválido: {tipo!r}.")
    if not isinstance(saldo_inicial, int) or isinstance(saldo_inicial, bool):
        raise ValueError("O saldo inicial deve ser um inteiro, em centavos.")
    try:
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO contas (nome, tipo, saldo_inicial) VALUES (%s, %s, %s)",
                (nome, tipo, saldo_inicial),
            )
            return cur.lastrowid
    except mysql_errors.IntegrityError:
        raise ValueError(f"Já existe uma conta chamada '{nome}'.") from None
    
def listar_contas() -> list[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT id, nome, tipo, saldo_inicial FROM contas ORDER BY nome")
        return cur.fetchall()


# ---------- transações ----------
_SELECT_TRANSACOES = """
    SELECT t.id, t.data, t.valor, t.tipo, t.descricao, t.forma_pagamento,
           t.categoria_id, c.nome AS categoria, t.conta_id, ct.nome AS conta
    FROM transacoes t
    JOIN categorias c ON c.id = t.categoria_id
    JOIN contas ct ON ct.id = t.conta_id
"""


def inserir_transacao(data, valor: int, tipo: str, categoria_id: int, conta_id: int,
                      descricao: str | None = None, forma_pagamento: str | None = None) -> int:
    with get_cursor() as cur:
        _validar_transacao(cur, valor, tipo, categoria_id)
        cur.execute(
            """INSERT INTO transacoes
               (data, valor, tipo, categoria_id, conta_id, descricao, forma_pagamento)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (data, valor, tipo, categoria_id, conta_id, descricao, forma_pagamento),
        )
        return cur.lastrowid


def buscar_transacao(transacao_id: int) -> dict | None:
    with get_cursor() as cur:
        cur.execute(_SELECT_TRANSACOES + " WHERE t.id = %s", (transacao_id,))
        return cur.fetchone()


def listar_transacoes(mes: str | None = None, tipo: str | None = None,
                      categoria_id: int | None = None, conta_id: int | None = None) -> list[dict]:
    sql = _SELECT_TRANSACOES + " WHERE 1 = 1"
    params = []
    if mes:
        inicio, fim = intervalo_do_mes(mes)
        sql += " AND t.data >= %s AND t.data < %s"
        params += [inicio, fim]
    if tipo:
        _validar_tipo(tipo)
        sql += " AND t.tipo = %s"
        params.append(tipo)
    if categoria_id:
        sql += " AND t.categoria_id = %s"
        params.append(categoria_id)
    if conta_id:
        sql += " AND t.conta_id = %s"
        params.append(conta_id)
    sql += " ORDER BY t.data DESC, t.id DESC"
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def atualizar_transacao(transacao_id: int, **campos) -> bool:
    """Altera só os campos informados. Devolve False se a transação não existir."""
    invalidos = set(campos) - CAMPOS_EDITAVEIS
    if invalidos:
        raise ValueError(f"Campos não editáveis: {', '.join(sorted(invalidos))}")
    if not campos:
        return False
    with get_cursor() as cur:
        cur.execute(
            """SELECT data, valor, tipo, categoria_id, conta_id, descricao, forma_pagamento
               FROM transacoes WHERE id = %s""",
            (transacao_id,),
        )
        atual = cur.fetchone()
        if atual is None:
            return False
        novo = {**atual, **campos}
        _validar_transacao(cur, novo["valor"], novo["tipo"], novo["categoria_id"])
        colunas = ", ".join(f"{coluna} = %s" for coluna in campos)  # nomes vêm da lista permitida
        cur.execute(
            f"UPDATE transacoes SET {colunas} WHERE id = %s",
            (*campos.values(), transacao_id),
        )
        return True


def excluir_transacao(transacao_id: int) -> bool:
    with get_cursor() as cur:
        cur.execute("DELETE FROM transacoes WHERE id = %s", (transacao_id,))
        return cur.rowcount > 0

    # ---------- agregações (usadas pelos serviços) ----------
def total_saldo_inicial() -> int:
    with get_cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(saldo_inicial), 0) AS total FROM contas")
        return int(cur.fetchone()["total"])


def somar_por_tipo(inicio=None, fim=None) -> dict:
    """Soma de entradas e saídas (em centavos) com inicio <= data < fim."""
    sql = "SELECT tipo, SUM(valor) AS total FROM transacoes WHERE 1 = 1"
    params = []
    if inicio:
        sql += " AND data >= %s"
        params.append(inicio)
    if fim:
        sql += " AND data < %s"
        params.append(fim)
    sql += " GROUP BY tipo"
    totais = {"entrada": 0, "saida": 0}
    with get_cursor() as cur:
        cur.execute(sql, params)
        for linha in cur.fetchall():
            totais[linha["tipo"]] = int(linha["total"])
    return totais


def totais_por_mes() -> list[dict]:
    """[{'mes': '2026-03', 'entradas': ..., 'saidas': ...}, ...] em ordem cronológica."""
    sql = """
        SELECT YEAR(data) AS ano, MONTH(data) AS mes,
               SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END) AS entradas,
               SUM(CASE WHEN tipo = 'saida' THEN valor ELSE 0 END) AS saidas
        FROM transacoes
        GROUP BY YEAR(data), MONTH(data)
        ORDER BY YEAR(data), MONTH(data)
    """
    with get_cursor() as cur:
        cur.execute(sql)
        return [
            {
                "mes": f"{linha['ano']:04d}-{linha['mes']:02d}",
                "entradas": int(linha["entradas"]),
                "saidas": int(linha["saidas"]),
            }
            for linha in cur.fetchall()
        ]


def gasto_por_categoria(inicio, fim, tipo: str = "saida") -> list[dict]:
    _validar_tipo(tipo)
    sql = """
        SELECT c.id AS categoria_id, c.nome AS categoria, SUM(t.valor) AS total
        FROM transacoes t
        JOIN categorias c ON c.id = t.categoria_id
        WHERE t.tipo = %s AND t.data >= %s AND t.data < %s
        GROUP BY c.id, c.nome
        ORDER BY total DESC, c.nome
    """
    with get_cursor() as cur:
        cur.execute(sql, (tipo, inicio, fim))
        return [{**linha, "total": int(linha["total"])} for linha in cur.fetchall()]
    
    # ---------- manutenção de categorias e contas ----------
def renomear_categoria(categoria_id: int, novo_nome: str) -> None:
    novo_nome = _nome_valido(novo_nome)
    try:
        with get_cursor() as cur:
            cur.execute("UPDATE categorias SET nome = %s WHERE id = %s", (novo_nome, categoria_id))
    except mysql_errors.IntegrityError:
        raise ValueError(f"Já existe uma categoria chamada '{novo_nome}'.") from None


def definir_categoria_ativa(categoria_id: int, ativa: bool) -> None:
    with get_cursor() as cur:
        cur.execute(
            "UPDATE categorias SET ativa = %s WHERE id = %s", (1 if ativa else 0, categoria_id)
        )


def atualizar_conta(conta_id: int, novo_nome: str, saldo_inicial: int) -> None:
    novo_nome = _nome_valido(novo_nome)
    if not isinstance(saldo_inicial, int) or isinstance(saldo_inicial, bool):
        raise ValueError("O saldo inicial deve ser um inteiro, em centavos.")
    try:
        with get_cursor() as cur:
            cur.execute(
                "UPDATE contas SET nome = %s, saldo_inicial = %s WHERE id = %s",
                (novo_nome, saldo_inicial, conta_id),
            )
    except mysql_errors.IntegrityError:
        raise ValueError(f"Já existe uma conta chamada '{novo_nome}'.") from None