"""CLI 入口
支持：单条问题、--demo、--session。
"""

import argparse
import json
import sys

from app.graph import get_pending, run_agent

DEMO_QUERIES = [
    "北京今天天气怎么样？需要带伞吗？",
    "帮我算一下 (23 * 4 + 10) / 2 等于多少",
    "知识库里是怎么解释 ReAct 循环的？",
    "杭州现在气温多少？再把摄氏温度换算成华氏度，公式是 C * 9 / 5 + 32，用计算工具算。",
]

def main():
    parser = argparse.ArgumentParser(description="生产级 Agent 服务 D1 基线")
    parser.add_argument("query", nargs="?", help="单条问题")
    parser.add_argument("--session", help="复用会话 ID")
    parser.add_argument("--demo", action="store_true", help="跑四条演示问题")
    args = parser.parse_args()

    if args.demo:
        queries = DEMO_QUERIES
    elif args.query:
        queries = [args.query]
    else:
        parser.print_help()
        return

    for query in queries:
        session_id, answer = run_agent(query, args.session)
        print("\n[session] %s" % session_id)
        print("[Q] %s" % query)

        pending = get_pending(session_id)
        if pending is not None:
            print("[待审批] %s" % json.dumps(pending, ensure_ascii=False))
            print("请执行: python -m app.approve --session %s --approve" % session_id)
            sys.exit(2)

        print("[A] %s" % answer)

if __name__ == "__main__":
    main()