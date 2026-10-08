from src.database.connection import get_cursor
from src.utils.datas import intervalo_do_mes

TIPOS = ("entrada", "saida")
CAMPOS_EDITAVEIS = {
    "data", "valor", "tipo", "categoria_id", "conta_id", "descricao", "forma_pagamento",
}


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
    with get_cursor() as cur:
        cur.execute("INSERT INTO categorias (nome, tipo) VALUES (%s, %s)", (nome, tipo))
        return cur.lastrowid


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
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO contas (nome, tipo, saldo_inicial) VALUES (%s, %s, %s)",
            (nome, tipo, saldo_inicial),
        )
        return cur.lastrowid


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