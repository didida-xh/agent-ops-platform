"""工具注册

用 @tool 包装 tools_base 的三个函数，导出 TOOLS 与 TOOL_REGISTRY。
"""

import json
import os
from pathlib import Path

from langchain_core.tools import tool

from app import tools_base
from app.config import ROOT

WORKSPACE = ROOT / "workspace"

@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气。国外城市请使用英文名。"""
    return json.dumps(tools_base.get_weather(city), ensure_ascii=False)

@tool
def calculate(expression: str) -> str:
    """计算数学表达式。涉及数字运算时必须使用本工具。"""
    return json.dumps(tools_base.calculate(expression), ensure_ascii=False)

@tool
def search_knowledge_base(query: str, top_k: int = 3) -> str:
    """检索本地综述中关于智能体、ReAct、RAG、工具调用的资料。"""
    return json.dumps(
        tools_base.search_knowledge_base(query, top_k),
        ensure_ascii=False,
    )

@tool
def write_file(path: str, content: str) -> str:
    """把文本内容写入 workspace 目录下的文件。path 必须是相对路径，不能包含 .. 或使用绝对路径。"""
    WORKSPACE.mkdir(exist_ok=True)
    if os.path.isabs(path) or ".." in Path(path).parts:
        return json.dumps(
            {"error": "路径不合法：只允许 workspace 内的相对路径"},
            ensure_ascii=False,
        )
    root = WORKSPACE.resolve()
    target = (root / path).resolve()
    if not str(target).startswith(str(root) + os.sep):
        return json.dumps({"error": "路径越界：%s" % path}, ensure_ascii=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return json.dumps(
        {"path": str(target.relative_to(root)), "bytes": len(content.encode("utf-8"))},
        ensure_ascii=False,
    )

TOOLS = [get_weather, calculate, search_knowledge_base, write_file]
TOOL_REGISTRY = {t.name: t for t in TOOLS}
HIGH_RISK_TOOLS = {"write_file"}