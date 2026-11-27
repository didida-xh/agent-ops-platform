"""工具注册

用 @tool 包装 tools_base 的三个函数，导出 TOOLS 与 TOOL_REGISTRY。
"""

import json

from langchain_core.tools import tool

from app import tools_base

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

TOOLS = [get_weather, calculate, search_knowledge_base]
TOOL_REGISTRY = {t.name: t for t in TOOLS}