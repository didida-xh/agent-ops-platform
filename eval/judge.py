"""评测判定器（纯函数，无 IO、不依赖数据库和模型）。

对外只暴露一个函数：

    judge(answer: str, tool_chain: list[str], rule: dict) -> tuple[bool, str]

rule["type"] 取值：
- "number"    比较回答中的数字，规则含 value、tolerance
- "contains"  回答必须包含 keywords 中全部关键词
- "toolchain" 比较工具调用序列与 expected 完全一致
- "all"       复合规则，rules 中所有子规则都通过才算通过

返回值：(是否通过, 原因)。原因用于报告和失败排查，不参与判定。
"""


import re

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

def _numbers(text):
    return [float(x) for x in NUM_RE.findall(text or "")]

def judge(answer, tool_chain, rule):
    """返回 (是否通过, 原因)。纯函数，不碰数据库。"""
    kind = rule["type"]

    if kind == "all":
        rules = rule.get("rules") or []
        if not rules:
            return False, "复合规则为空"
        for sub in rules:
            ok, why = judge(answer, tool_chain, sub)
            if not ok:
                return False, "子规则 %s 未通过：%s" % (sub.get("type"), why)
        return True, "全部子规则通过"

    if kind == "number":
        value = float(rule["value"])
        tol = float(rule.get("tolerance", 0))
        for num in _numbers(answer):
            if abs(num - value) <= tol:
                return True, "命中数值 %.6g" % num
        return False, "未命中 %.6g（容差 %s）" % (value, tol)

    if kind == "contains":
        missing = [k for k in rule["keywords"] if k not in (answer or "")]
        if missing:
            return False, "缺少关键词: %s" % ", ".join(missing)
        return True, "关键词齐全"

    if kind == "toolchain":
        expected = rule.get("expected", [])
        if tool_chain == expected:
            return True, "工具链一致"
        return False, "工具链 %s != %s" % (tool_chain, expected)

    raise ValueError("未知判定类型: %s" % kind)