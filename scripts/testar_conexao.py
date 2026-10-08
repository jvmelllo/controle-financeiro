from src.database.connection import get_cursor

with get_cursor() as cur:
    cur.execute("SELECT DATABASE() AS banco, CURRENT_USER() AS usuario")
    print(cur.fetchone())
    cur.execute("SHOW TABLES")
    print([list(linha.values())[0] for linha in cur.fetchall()])