"""高风险动作审批入口

用法：
    python -m app.approve --session s1 --approve
    python -m app.approve --session s1 --reject --note "路径不对"
"""

import argparse
import json

from langgraph.types import Command

from app.db import connect, ensure_schema
from app.events import ensure_session
from app.graph import build_graph, get_pending


def main():
    parser = argparse.ArgumentParser(description="审批挂起中的高风险动作")
    parser.add_argument("--session", required=True, help="会话 ID")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--approve", action="store_true", help="批准执行")
    group.add_argument("--reject", action="store_true", help="拒绝执行")
    parser.add_argument("--note", help="审批备注")
    args = parser.parse_args()

    pending = get_pending(args.session)
    if pending is None:
        print("会话 %s 没有待审批的请求" % args.session)
        return

    print("[待审批] %s" % json.dumps(pending, ensure_ascii=False))
    decision = "approved" if args.approve else "rejected"

    conn = connect()
    try:
        ensure_schema(conn)
        ensure_session(conn, args.session)
        graph = build_graph(conn, args.session)
        result = graph.invoke(
            Command(resume={"decision": decision, "note": args.note}),
            config={"recursion_limit": 20, "configurable": {"thread_id": args.session}},
        )
        print("[决策] %s" % decision)
        print("[A] %s" % result["messages"][-1].content)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
