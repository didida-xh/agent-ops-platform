"""评测指标（纯函数，输入是已经取出来的事件，不连数据库）。

输入 cases:
    [{"id": "e01", "passed": True,
      "events": [{"type": "tool_result", "error": ""}, ...]}, ...]

输出:
    param_error_rate  参数类错误 / 全部 tool_result
    recovery_rate     出过工具错误且最终通过的题 / 出过工具错误的题
    loop_rate         出现重复调用或触达递归上限的会话 / 全部会话

瞬时类错误（超时、连接失败、重复调用拦截）不算参数错误。
"""

TRANSIENT_PREFIXES = ("TimeoutError", "ConnectionError", "duplicate_call")
NOT_FOUND_PATTERNS = ("没有找到", "未找到", "not found")


def _is_transient(error):
    return any(error.startswith(p) for p in TRANSIENT_PREFIXES)


def _is_not_found(error):
    return any(p in error for p in NOT_FOUND_PATTERNS)


def _ratio(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def compute_metrics(cases):
    tool_results = [
        e for c in cases for e in c["events"] if e["type"] == "tool_result"
    ]
    param_errors = [
        e for e in tool_results
        if e.get("error")
        and not _is_transient(e["error"])
        and not _is_not_found(e["error"])
    ]
    not_found = [
        e for e in tool_results
        if e.get("error") and _is_not_found(e["error"])
    ]

    error_cases = [
        c for c in cases
        if any(e["type"] == "tool_result" and e.get("error") for e in c["events"])
    ]
    recovered = [c for c in error_cases if c["passed"]]

    loop_cases = [
        c for c in cases
        if any(
            e["type"] == "tool_result"
            and (e.get("error") or "").startswith(("duplicate_call", "Recursion"))
            for e in c["events"]
        )
    ]

    return {
        "param_error_rate": _ratio(len(param_errors), len(tool_results)),
        "param_errors": len(param_errors),
        "tool_results": len(tool_results),
        "not_found": len(not_found),
        "recovery_rate": _ratio(len(recovered), len(error_cases)),
        "recovered": len(recovered),
        "error_cases": len(error_cases),
        "loop_rate": _ratio(len(loop_cases), len(cases)),
        "loop_cases": len(loop_cases),
    }
