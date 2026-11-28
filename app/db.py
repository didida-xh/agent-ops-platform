"""数据库连接
"""
import psycopg
from app.config import PG_DSN, SQL_DIR
def connect():
    return psycopg.connect(PG_DSN, autocommit=False)

def ensure_schema(conn):
    for path in sorted(SQL_DIR.glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
    conn.commit()