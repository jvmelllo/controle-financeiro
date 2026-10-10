import re

from mysql.connector import errors as mysql_errors

from src.database.connection import get_cursor
from src.utils.datas import intervalo_do_mes
from src.utils.textos import normalizar_texto


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


def totais_por_mes(inicio=None, fim=None) -> list[dict]:
    """[{'mes': '2026-03', 'entradas': ..., 'saidas': ...}, ...] em ordem cronológica."""
    sql = """
        SELECT YEAR(data) AS ano, MONTH(data) AS mes,
               SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END) AS entradas,
               SUM(CASE WHEN tipo = 'saida' THEN valor ELSE 0 END) AS saidas
        FROM transacoes
        WHERE 1 = 1
    """
    params = []
    if inicio:
        sql += " AND data >= %s"
        params.append(inicio)
    if fim:
        sql += " AND data < %s"
        params.append(fim)
    sql += " GROUP BY YEAR(data), MONTH(data) ORDER BY YEAR(data), MONTH(data)"
    with get_cursor() as cur:
        cur.execute(sql, params)
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


def totais_por_dia(inicio=None, fim=None) -> list[dict]:
    """[{'data': date, 'entradas': ..., 'saidas': ...}, ...] só dos dias com movimento."""
    sql = """
        SELECT data,
               SUM(CASE WHEN tipo = 'entrada' THEN valor ELSE 0 END) AS entradas,
               SUM(CASE WHEN tipo = 'saida' THEN valor ELSE 0 END) AS saidas
        FROM transacoes
        WHERE 1 = 1
    """
    params = []
    if inicio:
        sql += " AND data >= %s"
        params.append(inicio)
    if fim:
        sql += " AND data < %s"
        params.append(fim)
    sql += " GROUP BY data ORDER BY data"
    with get_cursor() as cur:
        cur.execute(sql, params)
        return [
            {"data": linha["data"], "entradas": int(linha["entradas"]), "saidas": int(linha["saidas"])}
            for linha in cur.fetchall()
        ]

# ---------- orçamentos ----------
def _validar_mes(mes: str) -> None:
    if not isinstance(mes, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
        raise ValueError("Mês inválido. Use o formato AAAA-MM.")


def definir_orcamento(categoria_id: int, mes: str, limite: int) -> None:
    """Cria ou atualiza o limite de gasto de uma categoria de saída em um mês ('AAAA-MM')."""
    _validar_mes(mes)
    if not isinstance(limite, int) or isinstance(limite, bool) or limite <= 0:
        raise ValueError("O limite deve ser um inteiro positivo, em centavos.")
    with get_cursor() as cur:
        cur.execute("SELECT tipo FROM categorias WHERE id = %s", (categoria_id,))
        categoria = cur.fetchone()
        if categoria is None:
            raise ValueError("Categoria inexistente.")
        if categoria["tipo"] != "saida":
            raise ValueError("Só categorias de saída podem ter limite de gasto.")
        cur.execute(
            """INSERT INTO orcamentos (categoria_id, mes, limite) VALUES (%s, %s, %s)
               AS novo ON DUPLICATE KEY UPDATE limite = novo.limite""",
            (categoria_id, mes, limite),
        )


def remover_orcamento(categoria_id: int, mes: str) -> None:
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM orcamentos WHERE categoria_id = %s AND mes = %s", (categoria_id, mes)
        )


def listar_orcamentos(mes: str) -> list[dict]:
    _validar_mes(mes)
    sql = """
        SELECT o.categoria_id, c.nome AS categoria, o.limite
        FROM orcamentos o
        JOIN categorias c ON c.id = o.categoria_id
        WHERE o.mes = %s
        ORDER BY c.nome
    """
    with get_cursor() as cur:
        cur.execute(sql, (mes,))
        return [{**linha, "limite": int(linha["limite"])} for linha in cur.fetchall()]


def copiar_orcamentos(mes_origem: str, mes_destino: str) -> int:
    """Copia os limites de um mês para outro sem sobrescrever os já definidos.

    Devolve quantos limites foram copiados.
    """
    _validar_mes(mes_origem)
    _validar_mes(mes_destino)
    if mes_origem == mes_destino:
        return 0
    with get_cursor() as cur:
        cur.execute(
            """INSERT IGNORE INTO orcamentos (categoria_id, mes, limite)
               SELECT categoria_id, %s, limite FROM orcamentos WHERE mes = %s""",
            (mes_destino, mes_origem),
        )
        return cur.rowcount

# ---------- metas de reserva ----------
def _validar_centavos_positivos(valor, nome: str) -> None:
    if not isinstance(valor, int) or isinstance(valor, bool) or valor <= 0:
        raise ValueError(f"{nome} deve ser um inteiro positivo, em centavos.")


def _validar_percentual(percentual) -> None:
    if not 0 <= percentual <= 100:
        raise ValueError("O percentual deve estar entre 0 e 100.")


def criar_meta(nome: str, valor_alvo: int, prazo=None, percentual_entrada: float = 0) -> int:
    nome = _nome_valido(nome)
    _validar_centavos_positivos(valor_alvo, "O valor-alvo")
    _validar_percentual(percentual_entrada)
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO metas (nome, valor_alvo, prazo, percentual_entrada) VALUES (%s, %s, %s, %s)",
            (nome, valor_alvo, prazo, percentual_entrada),
        )
        return cur.lastrowid


def listar_metas() -> list[dict]:
    """Metas com o total já aportado em cada uma (valores em centavos)."""
    sql = """
        SELECT m.id, m.nome, m.valor_alvo, m.prazo, m.percentual_entrada,
               COALESCE(SUM(a.valor), 0) AS aportado
        FROM metas m
        LEFT JOIN aportes_meta a ON a.meta_id = m.id
        GROUP BY m.id, m.nome, m.valor_alvo, m.prazo, m.percentual_entrada
        ORDER BY m.nome, m.id
    """
    with get_cursor() as cur:
        cur.execute(sql)
        return [
            {
                **linha,
                "valor_alvo": int(linha["valor_alvo"]),
                "aportado": int(linha["aportado"]),
                "percentual_entrada": float(linha["percentual_entrada"]),
            }
            for linha in cur.fetchall()
        ]


def atualizar_meta(meta_id: int, nome: str, valor_alvo: int, prazo=None,
                   percentual_entrada: float = 0) -> None:
    nome = _nome_valido(nome)
    _validar_centavos_positivos(valor_alvo, "O valor-alvo")
    _validar_percentual(percentual_entrada)
    with get_cursor() as cur:
        cur.execute(
            """UPDATE metas SET nome = %s, valor_alvo = %s, prazo = %s, percentual_entrada = %s
               WHERE id = %s""",
            (nome, valor_alvo, prazo, percentual_entrada, meta_id),
        )


def excluir_meta(meta_id: int) -> None:
    """Apaga a meta e todos os seus aportes (na mesma transação)."""
    with get_cursor() as cur:
        cur.execute("DELETE FROM aportes_meta WHERE meta_id = %s", (meta_id,))
        cur.execute("DELETE FROM metas WHERE id = %s", (meta_id,))


def inserir_aporte(meta_id: int, data, valor: int) -> int:
    _validar_centavos_positivos(valor, "O valor da contribuição")
    with get_cursor() as cur:
        cur.execute("SELECT id FROM metas WHERE id = %s", (meta_id,))
        if cur.fetchone() is None:
            raise ValueError("Meta inexistente.")
        cur.execute(
            "INSERT INTO aportes_meta (meta_id, data, valor) VALUES (%s, %s, %s)",
            (meta_id, data, valor),
        )
        return cur.lastrowid


def listar_aportes(meta_id: int) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, data, valor FROM aportes_meta WHERE meta_id = %s ORDER BY data DESC, id DESC",
            (meta_id,),
        )
        return [{**linha, "valor": int(linha["valor"])} for linha in cur.fetchall()]


def excluir_aporte(aporte_id: int) -> None:
    with get_cursor() as cur:
        cur.execute("DELETE FROM aportes_meta WHERE id = %s", (aporte_id,))


def total_reservado() -> int:
    """Soma de todos os aportes em todas as metas (centavos)."""
    with get_cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(valor), 0) AS total FROM aportes_meta")
        return int(cur.fetchone()["total"])

def total_aportes_por_meta(inicio, fim) -> dict[int, int]:
    """Total contribuído a cada meta com inicio <= data < fim (centavos).
    Metas sem contribuição no período não aparecem no resultado."""
    with get_cursor() as cur:
        cur.execute(
            """SELECT meta_id, SUM(valor) AS total FROM aportes_meta
               WHERE data >= %s AND data < %s GROUP BY meta_id""",
            (inicio, fim),
        )
        return {linha["meta_id"]: int(linha["total"]) for linha in cur.fetchall()}

    


# ---------- importação em lote ----------
def inserir_transacoes_em_lote(conta_id: int, linhas: list[dict]) -> dict:
    """Insere várias transações de uma vez, tudo ou nada (uma única transação do banco).

    Cada linha traz data, valor, tipo, descricao, forma_pagamento e categoria_id ou,
    para uma categoria que ainda não existe, categoria_nova (o nome). Se qualquer linha
    falhar, nada é gravado, nem as categorias criadas.
    """
    criadas: dict[str, int] = {}  # nome normalizado -> id criado nesta importação
    with get_cursor() as cur:
        cur.execute("SELECT id FROM contas WHERE id = %s", (conta_id,))
        if cur.fetchone() is None:
            raise ValueError("Conta inexistente.")
        for linha in linhas:
            categoria_id = linha.get("categoria_id")
            if categoria_id is None:
                nome = _nome_valido(linha.get("categoria_nova"))
                chave = normalizar_texto(nome)
                if chave not in criadas:
                    _validar_tipo(linha["tipo"])
                    cur.execute("INSERT INTO categorias (nome, tipo) VALUES (%s, %s)", (nome, linha["tipo"]))
                    criadas[chave] = cur.lastrowid
                categoria_id = criadas[chave]
            _validar_transacao(cur, linha["valor"], linha["tipo"], categoria_id)
            cur.execute(
                """INSERT INTO transacoes
                   (data, valor, tipo, categoria_id, conta_id, descricao, forma_pagamento)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (linha["data"], linha["valor"], linha["tipo"], categoria_id, conta_id,
                 linha.get("descricao"), linha.get("forma_pagamento")),
            )
    return {"transacoes": len(linhas), "categorias_criadas": len(criadas)}
