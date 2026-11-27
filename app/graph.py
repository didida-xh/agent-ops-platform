"""ReAct 图与埋点
"""

import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from time import perf_counter
from typing import Annotated, Optional, TypedDict
from uuid import uuid4

from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import tools_condition

from app.db import connect, ensure_schema
from app.events import ensure_session, log_event
from app.llm import llm
from app.tools import TOOLS, TOOL_REGISTRY

SYSTEM_PROMPT = """你是一个会使用工具的助手。                                 
规则：                                                              
1. 查询天气必须调用 get_weather；                                         
2. 涉及数字计算必须调用 calculate，不要心算；                                    
3. 涉及 ReAct、RAG、智能体、工具调用等概念时，调用 search_knowledge_base；           
4. 工具返回 error 时，先根据错误信息修正参数再试；                                   
5. 资料不足时直接说明，不要编造。                                               
"""

llm_with_tools=llm.bind_tools(TOOLS)

MAX_TOOL_SECONDS = 12
_executor = ThreadPoolExecutor(max_workers=4)


def _sig(call):
    return "%s:%s" % (
        call["name"],
        json.dumps(call.get("args") or {}, sort_keys=True, ensure_ascii=False),
    )


def _repeated_signatures(messages):
    ai_messages = [m for m in messages if getattr(m, "tool_calls", None)]
    if len(ai_messages) < 2:
        return set()
    prev = {_sig(c) for c in ai_messages[-2].tool_calls}
    cur = {_sig(c) for c in ai_messages[-1].tool_calls}
    return cur & prev


class State(TypedDict):
    messages:Annotated[list[AnyMessage],add_messages]
    session_id:str

def build_graph(conn,session_id:str):
    def agent_node(state:State):
        messages=[SystemMessage(content=SYSTEM_PROMPT)]+state["messages"]
        started=perf_counter()
        response=llm_with_tools.invoke(messages)
        log_event(
            conn,session_id,"model_decision","agent",
            result={
                "content":response.content,
                "tool_calls":[
                    {"name":c["name"],"args":c.get("args")}
                    for c in response.tool_calls
                ],
            },
            latency_ms=int((perf_counter() - started)*1000),
            tokens=response.usage_metadata,
        )
        return {"messages":[response]}

    def tools_node(state:State):
        last=state["messages"][-1]
        repeated = _repeated_signatures(state["messages"])
        results=[]
        for call in last.tool_calls:
            name=call["name"]
            args=call.get("args") or {}
            log_event(conn,session_id,"tool_call","agent",tool=name,args=args)
            started=perf_counter()

            if _sig(call) in repeated:
                content = json.dumps(
                    {"error": "检测到重复调用，已跳过执行。请更换参数或直接回答。"},
                    ensure_ascii=False,
                )
                log_event(
                    conn, session_id, "tool_result", "tool", tool=name,
                    error="duplicate_call",
                    latency_ms=0,
                )
                results.append(ToolMessage(content=content, tool_call_id=call["id"]))
                continue

            try:
                tool_fn=TOOL_REGISTRY.get(name)
                if tool_fn is None:
                    raise KeyError("未知工具：%s" %name)
                content = None
                last_exc = None
                for attempt in range(2):
                    try:
                        future = _executor.submit(tool_fn.invoke, args)
                        content = future.result(timeout=MAX_TOOL_SECONDS)
                        break
                    except FuturesTimeout:
                        future.cancel()
                        last_exc = TimeoutError("工具执行超过 %ss" % MAX_TOOL_SECONDS)
                    except (ConnectionError, OSError) as exc:
                        last_exc = exc
                if content is None:
                    raise last_exc or TimeoutError("工具执行失败")
                tool_error = None
                try:
                    payload = json.loads(content) if isinstance(content, str) else None
                    if isinstance(payload, dict) and payload.get("error"):
                        tool_error = str(payload["error"])
                except json.JSONDecodeError:
                    pass
                log_event(
                    conn, session_id, "tool_result", "tool", tool=name,
                    result=content,
                    error=tool_error,
                    latency_ms=int((perf_counter() - started) * 1000),
                )
            except Exception as exc:
                content = json.dumps(
                    {"error": "%s: %s" % (type(exc).__name__, exc)},
                    ensure_ascii=False,
                )
                log_event(
                    conn, session_id, "tool_result", "tool", tool=name,
                    error="%s: %s" % (type(exc).__name__, exc),
                    latency_ms=int((perf_counter() - started) * 1000),
                )

            results.append(ToolMessage(content=content, tool_call_id=call["id"]))
        return {"messages": results}

    builder=StateGraph(State)
    builder.add_node("agent",agent_node)
    builder.add_node("tools",tools_node)
    builder.add_edge(START,"agent")
    builder.add_conditional_edges("agent",tools_condition)
    builder.add_edge("tools","agent")
    return builder.compile()

def run_agent(user_input:str,session_id:Optional[str]=None):
    sid = session_id or "s" + uuid4().hex[:8]
    conn=connect()
    try:
        ensure_schema(conn)
        ensure_session(conn, sid)
        log_event(conn, sid, "user_input", "user", result={"text": user_input})

        graph=build_graph(conn,sid)
        result = graph.invoke(
            {"messages": [("user", user_input)], "session_id": sid},
            config={"recursion_limit": 20},
        )
        return sid, result["messages"][-1].content
    except Exception as exc:
        try:
            log_event(conn, sid, "error", "system",
                      error="%s: %s" % (type(exc).__name__, exc))
        except Exception:
            pass
        raise
    finally:
        conn.close()






















