"""回放 CLI

用法：python -m app.replay <session_id>
只读 events 表，不调模型。
"""


import json
import sys

from app.db import connect

def _short(value, limit=140):
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "..."

def _detail(event_type, tool, args, result, latency_ms, error):
    if event_type == "user_input":
        return _short(result.get("text") if isinstance(result, dict) else result)
    if event_type == "model_decision":
        calls = (result or {}).get("tool_calls") or []
        if calls:
            return "tool_calls=" + ",".join(c["name"] for c in calls)
        return "final: " + _short((result or {}).get("content"))
    if event_type == "tool_call":
        return "%s %s" % (tool, _short(args))
    if event_type == "tool_result":
        status = "ERR" if error else "ok"
        tail = error if error else _short(result)
        return "%s %s %sms %s" % (tool, status, latency_ms, tail)
    return _short(error or result)

def main():
    if len(sys.argv) != 2:
        print("用法: python -m app.replay <session_id>")
        return

    session_id = sys.argv[1]
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT seq, type, source, tool, args, result,
                   latency_ms, tokens, error, created_at
            FROM events WHERE session_id = %s ORDER BY seq
            """,
            (session_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("没有找到会话 %s 的事件" % session_id)
        return

    print("# session %s（%d 步）" % (session_id, len(rows)))
    for seq, event_type, _source, tool, args, result, latency_ms, _tokens, error, created_at in rows:
        mark = "!! " if (event_type == "error" or error) else "   "
        detail = _detail(event_type, tool, args, result, latency_ms, error)
        print("%s#%-3d %s %-14s %s" % (
            mark, seq, created_at.strftime("%H:%M:%S"), event_type, detail,
        ))

if __name__ == "__main__":
    main()

