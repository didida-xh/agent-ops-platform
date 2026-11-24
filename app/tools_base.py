
##1.天气查询
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODE = {
    0: "晴", 1: "大部晴朗", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    80: "阵雨", 81: "强阵雨", 82: "暴雨",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "强雷暴伴冰雹",
}

def get_weather(city:str)-> dict:
    city=city.strip()
    if not city:
        return {"error":"city 为空"}
    try:
        with httpx.Client(trust_env=False, timeout=20) as client:
            geo = client.get(
                GEO_URL,
                params={"name": city, "count": 1, "language": "zh", "format": "json"},
            )
            geo.raise_for_status()
            results = geo.json().get("results") or []
            if not results:
                return {"city": city, "error": ",没有找到该城市"}

            place = results[0]
            weather = client.get(
                WEATHER_URL,
                params={
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,relative_humidity_2m,weather_code",
                    "timezone": "auto",
                },
            )
            weather.raise_for_status()
            current = weather.json()["current"]
    except Exception as exc:
        return {"city": city, "error": f"{type(exc).__name__}: {exc}"}


    code = current.get("weather_code")
    return {
        "city": place.get("name", city),
        "country": place.get("country"),
        "source": "open-meteo",
        "weather": WEATHER_CODE.get(code, f"未知天气码 {code}"),
        "temperature_c": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "observed_at": current.get("time"),
    }

##2.算数
import re

_ALLOWED = re.compile(r"[0-9+\-*/(). %]+")

def calculate(expression: str) -> dict:
    expression = expression.strip()
    if not expression or len(expression) > 100:
        return {"error": "表达式为空或过长"}
    if "**" in expression:
        return {"error": "暂不支持乘方运算"}
    if not _ALLOWED.fullmatch(expression):
        return {"error": "只支持数字和 + - * / % ( )"}

    try:
        result = eval(expression, {"__builtins__": {}}, {})
    except Exception as exc:
        return {"expression": expression, "error": f"计算失败: {exc}"}

    if isinstance(result, bool) or not isinstance(result, (int, float)):
        return {"expression": expression, "error": "结果不是实数"}

    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return {"expression": expression, "result": result}


##3.Rag文档库查询
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

BASE = Path(__file__).resolve().parent
# 优先用本目录的 .env，找不到就用上层的（仓库统一放一份）
for _env_path in (BASE / ".env", BASE.parent / ".env"):
    if _env_path.exists():
        load_dotenv(_env_path)
        break

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("EMBEDDING_BASE_URL"),
    http_client=httpx.Client(trust_env=False, timeout=60),
)
MODEL = os.getenv("EMBEDDING_MODEL")

def _embed(texts):
    vectors=[]
    for i in range(0,len(texts),10):
        resp=client.embeddings.create(model=MODEL,input=texts[i:i+10])
        vectors.extend(item.embedding for item in resp.data)
    return vectors

# 1. 切块
_text = (BASE / "知识库" / "llm-agents-survey-zh.md").read_text(encoding="utf-8")
_chunks=[_text[i:i+1000] for i in range(0,len(_text),1000)]

#2.存储
_vectors=_embed(_chunks)

#3.检索
def search_knowledge_base(query:str,top_k:int=3)-> dict:
    if not query.strip():
        return {"error":"query为空"}

    q=_embed([query])[0]
    scores=[sum(a*b for a,b in zip(q,v)) for v in _vectors]
    top=sorted(range(len(scores)),key=lambda i: scores[i],reverse=True)[:top_k]
    return {
        "query":query,
        "hits":[
            {"score":round(scores[i],4),"content":_chunks[i]}
            for i in top
        ],
    }




TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的实时天气。国外城市请使用英文名，例如 New York、Paris。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如：北京、上海、New York"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算数学表达式。凡是涉及数字运算，都必须调用本工具，不要心算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，如：(23*4+10)/2"},
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "在本地综述中检索智能体、ReAct、RAG、工具调用等概念的资料。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索问题或关键词"},
                    "top_k": {"type": "integer", "description": "返回条数，默认 3", "default": 3},
                },
                "required": ["query"],
            },
        },
    },
]

TOOL_REGISTRY = {
    "get_weather": get_weather,
    "calculate": calculate,
    "search_knowledge_base": search_knowledge_base,
}






















