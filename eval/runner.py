"""评测执行器。

职责：
1. 读 eval/dataset.jsonl
2. 逐条调用 app.graph.run_agent，session_id 必须带本次 run_id，避免事件累加
3. 从 events 表取该会话的 tool_call 序列（按 seq 排序）
4. 调 eval.judge.judge 判定
5. 汇总总通过率、分难度通过率、平均工具轮次、失败明细
6. 报告写入 reports/report_<run_id>.json（该目录已在 .gitignore 中）

运行方式：python -m eval.runner
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.db import connect
from app.graph import run_agent
from eval.judge import judge
from eval.metrics import compute_metrics

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "eval" / "dataset.jsonl"
REPORT_DIR = ROOT / "reports"

def load_dataset():
    with open(DATASET, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def tool_chain_of(conn, session_id):
    rows = conn.execute(
        "SELECT tool FROM events WHERE session_id = %s AND type = 'tool_call' ORDER BY seq",
        (session_id,),
    ).fetchall()
    return [r[0] for r in rows]

def events_of(conn, session_id):
    rows = conn.execute(
        "SELECT type, error FROM events WHERE session_id = %s ORDER BY seq",
        (session_id,),
    ).fetchall()
    return [{"type": r[0], "error": r[1] or ""} for r in rows]

def run_case(case, run_id):
    session_id = "eval_%s_%s" % (case["id"], run_id)
    error = None
    try:
        _, answer = run_agent(case["query"], session_id)
    except Exception as exc:
        answer = ""
        error = "%s: %s" % (type(exc).__name__, exc)

    conn = connect()
    try:
        chain = tool_chain_of(conn, session_id)
        events = events_of(conn, session_id)
    finally:
        conn.close()

    if error:
        return {"id": case["id"], "level": case["level"], "passed": False,
                "reason": "运行异常: " + error, "tool_chain": chain,
                "answer": answer[:200], "events": events}

    passed, reason = judge(answer, chain, case["judge"])
    return {"id": case["id"], "level": case["level"], "passed": passed,
            "reason": reason, "tool_chain": chain, "answer": answer[:200],
            "events": events}

def summarize(results):
    by_level = defaultdict(lambda: {"total": 0, "passed": 0})
    for item in results:
        bucket = by_level[item["level"]]
        bucket["total"] += 1
        bucket["passed"] += int(item["passed"])

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    turns = [len(r["tool_chain"]) for r in results if r["passed"]]
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "avg_tool_calls": round(sum(turns) / len(turns), 2) if turns else 0,
        "by_level": {
            k: {"total": v["total"], "passed": v["passed"],
                "rate": round(v["passed"] / v["total"], 4)}
            for k, v in by_level.items()
        },
        "failures": [r for r in results if not r["passed"]],
        **compute_metrics(results),
    }

def main():
    run_id = datetime.now().strftime("%m%d%H%M%S")
    results = [run_case(case, run_id) for case in load_dataset()]
    clean = [{k: v for k, v in r.items() if k != "events"} for r in results]
    report = {"run_id": run_id, "results": clean, "summary": summarize(results)}

    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / ("report_%s.json" % run_id)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = report["summary"]
    print("run_id=%s  通过 %d/%d（%.1f%%）  平均工具轮次 %.2f"
          % (run_id, summary["passed"], summary["total"],
             summary["pass_rate"] * 100, summary["avg_tool_calls"]))
    for level, stat in sorted(summary["by_level"].items()):
        print("  %-6s %d/%d  %.1f%%" % (level, stat["passed"], stat["total"], stat["rate"] * 100))
    print("  参数错误率 %s（%d/%d，另有未找到 %d）  失败恢复率 %s（%d/%d）  死循环 %s（%d 个会话）"
          % (summary["param_error_rate"], summary["param_errors"], summary["tool_results"],
             summary["not_found"],
             summary["recovery_rate"], summary["recovered"], summary["error_cases"],
             summary["loop_rate"], summary["loop_cases"]))
    for fail in summary["failures"]:
        print("  !! %s  %s" % (fail["id"], fail["reason"]))
    print("报告: %s" % path)

if __name__ == "__main__":
    main()