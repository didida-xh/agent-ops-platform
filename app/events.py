"""事件写入层
"""


import json
from typing import Any, Optional

from psycopg.types.json import Jsonb

MAX_PAYLOAD_BYTES = 2048

def _to_jsonb(value: Any):
    """转成 JSONB 可存的结构。返回 (Jsonb 或 None, 是否截断)。"""
    if value is None:
        return None,False
    text=value if isinstance(value,str) else json.dumps(
        value, ensure_ascii=False, default=str
    )
    raw=text.encode("utf-8")
    if len(raw)>MAX_PAYLOAD_BYTES:
        clipped = raw[:MAX_PAYLOAD_BYTES].decode("utf-8", errors="ignore")
        return Jsonb({"truncated": True, "text": clipped}), True

    try:
        return Jsonb(json.loads(text)), False
    except json.JSONDecodeError:
        return Jsonb({"text": text}), False

def ensure_session(conn,session_id:str,version:str="v1",rollout_group:str="control"):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sessions (session_id, version, rollout_group)
            VALUES (%s, %s, %s)
            ON CONFLICT (session_id) DO NOTHING
            """,
            (session_id, version, rollout_group),
        )
    conn.commit()


def log_event(conn, session_id: str, event_type: str, source: str,
              tool: Optional[str] = None, args: Any = None, result: Any = None,
              latency_ms: Optional[int] = None, tokens: Any = None,
              error: Optional[str] = None) -> int:
    args_payload, args_trunc = _to_jsonb(args)
    result_payload, result_trunc = _to_jsonb(result)
    tokens_payload, tokens_trunc = _to_jsonb(tokens)

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (session_id,))
            cur.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id = %s",
                (session_id,),
            )
            seq = cur.fetchone()[0]
            cur.execute(
                """                                                                                           
                INSERT INTO events                                                                            
                  (session_id, seq, type, source, tool, args, result,                                         
                   latency_ms, tokens, error, truncated)                                                      
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)                                           
                """,
                (
                    session_id, seq, event_type, source, tool,
                    args_payload, result_payload, latency_ms,
                    tokens_payload, error,
                    args_trunc or result_trunc or tokens_trunc,
                ),
            )
    return seq







